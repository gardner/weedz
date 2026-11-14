"""A model bundle's manifest: canonical bytes, Ed25519 signatures and the device's checks (#59)."""

import base64
import json
from datetime import date
from pathlib import Path

import pytest
from bundle_helpers import VARIANT, parity_benchmark, spec, write_artefacts
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from weedz.bundles.canonical import canonical
from weedz.bundles.manifest import (
    PAYLOAD_TYPE,
    BundleRejected,
    ParityRefused,
    artefact,
    build_manifest,
    check_artefact,
    parity_record,
    read_manifest,
    screening_stamp,
)
from weedz.bundles.signing import public_key_text, sign, verify
from weedz.discovery.inference import MODELS, RANKING_REVISION
from weedz.discovery.records import SPECIES

TODAY = date(2026, 11, 14)


@pytest.fixture
def key() -> Ed25519PrivateKey:
    return Ed25519PrivateKey.generate()


def test_canonical_bytes_do_not_depend_on_key_order_or_whitespace() -> None:
    first = canonical({"b": [1, {"y": True, "x": None}], "a": "kōwhai"})
    second = canonical(json.loads(' { "a" : "kōwhai", "b": [1, {"x": null, "y": true}] } '))
    assert first == second == '{"a":"kōwhai","b":[1,{"x":null,"y":true}]}'.encode()


@pytest.mark.parametrize("value", [1.5, float("nan"), 2**53, {1: "key"}, {"ā": 1}, (1, 2)])
def test_canonical_refuses_values_another_language_could_encode_differently(value) -> None:
    with pytest.raises(ValueError):
        canonical({"value": value})


def test_a_signed_payload_verifies_against_its_pinned_key(key: Ed25519PrivateKey) -> None:
    envelope = sign(b'{"a":1}', key)
    assert verify(envelope, [public_key_text(key)]) == b'{"a":1}'
    assert envelope["payloadType"] == PAYLOAD_TYPE


def test_a_tampered_payload_or_type_fails(key: Ed25519PrivateKey) -> None:
    envelope = sign(b'{"sequence":2}', key)
    forged = envelope | {"payload": base64.b64encode(b'{"sequence":3}').decode()}
    with pytest.raises(BundleRejected, match="signature"):
        verify(forged, [public_key_text(key)])
    with pytest.raises(BundleRejected, match="type"):
        verify(envelope | {"payloadType": "application/json"}, [public_key_text(key)])


def test_a_signature_from_an_unpinned_key_fails(key: Ed25519PrivateKey) -> None:
    other = Ed25519PrivateKey.generate()
    envelope = sign(b"{}", other)
    with pytest.raises(BundleRejected, match="signature"):
        verify(envelope, [public_key_text(key)])
    assert verify(envelope, [public_key_text(key), public_key_text(other)]) == b"{}"


def test_the_screening_stamp_is_what_an_intake_report_carries() -> None:
    stamp = screening_stamp("bioclip-2")
    assert stamp == {
        "model_key": "bioclip-2",
        "revision": MODELS["bioclip-2"]["revision"],
        "ranking_revision": RANKING_REVISION,
        "score_meaning": "bioclip-2/ranking-4/meaning-1",
    }


def test_the_screening_stamp_validates_as_an_intake_report_model() -> None:
    schema = pytest.importorskip("weedz.intake.schema", reason="intake (#57) not merged yet")
    assert schema.Screening.model_validate(screening_stamp("bioclip-2"))


def test_publishing_is_refused_without_a_passing_parity_record(tmp_path: Path) -> None:
    tower, _ = write_artefacts(tmp_path)
    digest = artefact(tower)["sha256"]
    passing = json.loads(parity_benchmark(tmp_path, tower).read_text())
    assert parity_record(passing, VARIANT, "bioclip-2", digest) == "onnx-fp16/thresholds-1"
    failing = json.loads(parity_benchmark(tmp_path, tower, passed=False).read_text())
    refusals = [
        (passing, "torch-int8", digest, "no parity record"),
        (failing, VARIANT, digest, "did not pass"),
        (passing, VARIANT, "0" * 64, "other bytes"),
    ]
    for benchmark, variant, sha, reason in refusals:
        with pytest.raises(ParityRefused, match=reason):
            parity_record(benchmark, variant, "bioclip-2", sha)


@pytest.mark.parametrize(
    "override",
    [
        {"artefact_sha256": None},
        {"revision": "0" * 40},
        {"parity": {"thresholds": {"version": 0}, "passed": True}},
    ],
)
def test_a_record_for_other_bytes_model_or_thresholds_cannot_gate(tmp_path: Path, override) -> None:
    tower, _ = write_artefacts(tmp_path)
    benchmark = json.loads(parity_benchmark(tmp_path, tower, **override).read_text())
    with pytest.raises(ParityRefused):
        parity_record(benchmark, VARIANT, "bioclip-2", artefact(tower)["sha256"])


def test_the_manifest_lists_every_part_and_is_stable(tmp_path: Path) -> None:
    manifest = build_manifest(spec(tmp_path))
    assert set(manifest) >= {
        "schema",
        "sequence",
        "expires",
        "min_app_version",
        "region",
        "watchlist",
        "lookalikes",
        "comparisons",
        "screening",
        "image_model",
        "text_table",
    }
    assert [item["taxon"] for item in manifest["watchlist"]] == list(SPECIES)
    assert manifest["image_model"]["parity"] == "onnx-fp16/thresholds-1"
    assert manifest["text_table"]["shape"] == [len(manifest["text_table"]["prompts"]), 4]
    assert canonical(manifest) == canonical(build_manifest(spec(tmp_path)))


def test_a_text_table_that_does_not_fit_the_prompts_is_refused(tmp_path: Path) -> None:
    bundle = spec(tmp_path)
    Path(bundle.text_table).write_bytes(b"\0" * 6)
    with pytest.raises(ValueError, match="prompt"):
        build_manifest(bundle)


def test_artefact_hashes_and_sizes_are_checked(tmp_path: Path) -> None:
    tower, _ = write_artefacts(tmp_path)
    entry = artefact(tower)
    check_artefact(tower, entry)
    tower.write_bytes(tower.read_bytes()[:-1] + b"!")
    with pytest.raises(BundleRejected, match="SHA-256"):
        check_artefact(tower, entry)
    tower.write_bytes(b"short")
    with pytest.raises(BundleRejected, match="size"):
        check_artefact(tower, entry)


def _signed(tmp_path: Path, key: Ed25519PrivateKey, **override) -> dict:
    return sign(canonical(build_manifest(spec(tmp_path, **override))), key)


def test_the_device_reads_a_current_bundle(tmp_path: Path, key: Ed25519PrivateKey) -> None:
    envelope = _signed(tmp_path, key, sequence=3)
    trusted = [public_key_text(key)]
    manifest = read_manifest(envelope, trusted, today=TODAY, installed=2, app_version="0.2.0")
    assert manifest["sequence"] == 3


@pytest.mark.parametrize(
    ("installed", "app_version", "today", "reason"),
    [
        (3, "0.2.0", TODAY, "older"),
        (2, "0.0.9", TODAY, "app"),
        (2, "0.2.0", date(2027, 2, 15), "expired"),
    ],
)
def test_the_device_refuses_rollback_old_apps_and_expired_bundles(
    tmp_path: Path, key: Ed25519PrivateKey, installed, app_version, today, reason
) -> None:
    envelope = _signed(tmp_path, key, sequence=3)
    with pytest.raises(BundleRejected, match=reason):
        read_manifest(
            envelope,
            [public_key_text(key)],
            today=today,
            installed=installed,
            app_version=app_version,
        )


def test_the_device_refuses_an_unknown_schema(tmp_path: Path, key: Ed25519PrivateKey) -> None:
    manifest = build_manifest(spec(tmp_path)) | {"schema": 2}
    with pytest.raises(BundleRejected, match="schema"):
        read_manifest(
            sign(canonical(manifest), key),
            [public_key_text(key)],
            today=TODAY,
            installed=0,
            app_version="9.0.0",
        )
