"""Publication authenticates inside its client context before persisting any mutation intent."""

import httpx
import pytest
from test_annotation_samples import canonical_batch as canonical_batch
from test_publication_package import exported, manifest_sha

from weedz.batches.label_client import LabelStudioClient
from weedz.batches.package import validate_package
from weedz.batches.publisher_runtime import publisher_from_config


def test_failed_initial_authentication_leaves_no_uncertain_intent(
    canonical_batch, tmp_path, monkeypatch
):
    import weedz.batches.publisher_runtime as module

    package = validate_package(
        exported(canonical_batch, tmp_path), manifest_sha(tmp_path / "export")
    )
    token = tmp_path / "token"
    token.write_text("private-test-token", encoding="utf-8")
    token.chmod(0o600)
    transport = httpx.MockTransport(lambda request: httpx.Response(503))
    monkeypatch.setattr(
        module,
        "LabelStudioClient",
        lambda url, path: LabelStudioClient(url, path, transport=transport),
    )
    publish = publisher_from_config(
        {
            "project_id": 1,
            "api_url": "http://127.0.0.1:8068",
            "token_file": str(token),
            "database": str(tmp_path / "not-needed.sqlite3"),
            "images": str(tmp_path / "published"),
            "state": str(tmp_path / "state"),
            "lock": str(tmp_path / "writer.lock"),
        }
    )
    with pytest.raises(RuntimeError, match="authentication failed"):
        publish(package, 1)
    assert not (tmp_path / "state").exists()
    assert not (tmp_path / "writer.lock").exists()


def test_optional_legacy_reference_is_forwarded_without_mutating_configuration(monkeypatch):
    from pathlib import Path

    import weedz.batches.publisher_runtime as module
    from weedz.batches.package import Package

    reference = {"path": "/private/approved.json", "sha256": "a" * 64}
    config = {
        "project_id": 1,
        "api_url": "http://127.0.0.1:8068",
        "token_file": "/private/token",
        "database": "/private/db",
        "images": "/private/images",
        "state": "/private/state",
        "lock": "/private/lock",
        "legacy_identity_allowlist": reference,
    }
    observed = []

    class Client:
        def __init__(self, *args):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def refresh(self):
            pass

    monkeypatch.setattr(module, "LabelStudioClient", Client)
    monkeypatch.setattr(module, "publish", lambda *a, **kw: observed.append(kw) or {})
    module.publisher_from_config(config)(Package(Path("/unused"), "a" * 64, (), {}), 1)
    assert observed[0]["legacy_allowlist"] == reference
    assert config["legacy_identity_allowlist"] == reference
