"""Remote reviewers sign in with an invite token, and records carry their verified name."""

import logging
import sqlite3
import typing
from pathlib import Path

import pytest
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient
from test_review_attribution import store_with_photo

from weedz.discovery import access
from weedz.discovery.access import ATTRIBUTION_FIELDS, Access
from weedz.discovery.api import create_app
from weedz.discovery.records import ReviewerName


def signed_in(root: Path, name: str = "Ana") -> tuple[TestClient, str]:
    token = Access(root).invite(name).token
    return TestClient(create_app(root, access="tokens")), token


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_an_invite_is_stored_only_as_a_hash(tmp_path: Path) -> None:
    invite = Access(tmp_path).invite(" Ana ")
    assert invite.reviewer == "Ana"
    assert invite.token.startswith(f"weedz_{invite.id}_")
    assert invite.token not in repr(invite)
    secret = invite.token.rsplit("_", 1)[-1]
    with sqlite3.connect(tmp_path / "access.sqlite3") as db:
        rows = db.execute("SELECT * FROM reviewer_tokens").fetchall()
    assert secret not in repr(rows)
    assert (tmp_path / "access.sqlite3").stat().st_mode & 0o077 == 0
    assert Access(tmp_path).reviewer(invite.token) == "Ana"


def test_each_invite_is_new_and_names_are_checked(tmp_path: Path) -> None:
    store = Access(tmp_path)
    assert store.invite("Ana").token != store.invite("Ana").token
    with pytest.raises(ValueError):
        store.invite("   ")
    with pytest.raises(ValueError):
        store.invite("x" * 81)


@pytest.mark.parametrize(
    "presented",
    ["", "weedz", "weedz_1", "weedz_1_", "weedz_x_secret", "weedz_99_secret", "other_1_x"],
)
def test_unknown_or_malformed_tokens_name_no_one(tmp_path: Path, presented: str) -> None:
    Access(tmp_path).invite("Ana")
    assert Access(tmp_path).reviewer(presented) is None


def test_a_wrong_secret_for_a_real_id_is_refused(tmp_path: Path) -> None:
    invite = Access(tmp_path).invite("Ana")
    last = "B" if invite.token.endswith("A") else "A"
    assert Access(tmp_path).reviewer(invite.token[:-1] + last) is None
    assert Access(tmp_path).reviewer(f"weedz_{invite.id}_wrong") is None


def test_revoked_tokens_are_refused_at_once(tmp_path: Path) -> None:
    store = Access(tmp_path)
    kept, revoked = store.invite("Ana"), store.invite("Ana")
    assert store.revoke(revoked.id)
    assert not store.revoke(revoked.id)
    assert not store.revoke(999)
    assert store.reviewer(revoked.token) is None
    assert store.reviewer(kept.token) == "Ana"
    listed = {row["id"]: row for row in store.reviewers()}
    assert listed[revoked.id]["revoked_at"] and listed[kept.id]["revoked_at"] is None


def test_hashes_are_compared_in_constant_time(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[tuple[str, str]] = []

    def compare(a: str, b: str) -> bool:
        calls.append((a, b))
        return a == b

    monkeypatch.setattr(access.hmac, "compare_digest", compare)
    invite = Access(tmp_path).invite("Ana")
    assert Access(tmp_path).reviewer(invite.token) == "Ana"
    assert Access(tmp_path).reviewer(f"weedz_{invite.id}_wrong") is None
    # An unknown id still costs a comparison, so timing does not reveal which ids exist.
    assert Access(tmp_path).reviewer("weedz_99_wrong") is None
    assert len(calls) == 3


def test_the_listing_never_shows_a_token_or_its_hash(tmp_path: Path) -> None:
    invite = Access(tmp_path).invite("Ana")
    [row] = Access(tmp_path).reviewers()
    assert set(row) == {"id", "reviewer", "created_at", "revoked_at"}
    assert invite.token.rsplit("_", 1)[-1] not in repr(row)


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("get", "/runs"),
        ("get", "/session"),
        ("get", "/runs/run"),
        ("get", "/runs/run/export"),
        ("get", "/runs/run/photos/p/image"),
        ("get", "/studies"),
        ("post", "/runs"),
        ("post", "/runs/run/photos/p/review"),
    ],
)
def test_without_a_token_every_route_answers_401(tmp_path: Path, method: str, path: str) -> None:
    client, _token = signed_in(tmp_path)
    response = getattr(client, method)(path)
    assert response.status_code == 401
    assert response.headers["WWW-Authenticate"] == "Bearer"


@pytest.mark.parametrize(
    "header", ["Bearer", "Bearer ", "Basic weedz_1_x", "Bearer weedz_1_x", "weedz_1_x"]
)
def test_a_bad_authorization_header_answers_401(tmp_path: Path, header: str) -> None:
    client, _token = signed_in(tmp_path)
    assert client.get("/runs", headers={"Authorization": header}).status_code == 401


def test_a_revoked_token_cannot_read_or_write(tmp_path: Path) -> None:
    _store, photo_id = store_with_photo(tmp_path)
    client, token = signed_in(tmp_path)
    assert client.get("/runs", headers=bearer(token)).status_code == 200
    [row] = Access(tmp_path).reviewers()
    Access(tmp_path).revoke(row["id"])
    assert client.get("/runs", headers=bearer(token)).status_code == 401
    body = {"status": "confirmed", "reviewer": "Ana"}
    response = client.post(f"/runs/run/photos/{photo_id}/review", json=body, headers=bearer(token))
    assert response.status_code == 401


def test_a_signed_in_reviewer_writes_under_their_own_name(tmp_path: Path) -> None:
    store, photo_id = store_with_photo(tmp_path)
    client, token = signed_in(tmp_path)
    path = f"/runs/run/photos/{photo_id}/review"
    body = {"status": "confirmed", "reviewer": " Ana "}
    assert client.post(path, json=body, headers=bearer(token)).status_code == 200
    assert [event["reviewer"] for event in store.reviews("run", photo_id)] == ["Ana"]


@pytest.mark.parametrize("disguised", ["Ana\x1f", "Ana\x1c", "\x1dAna"])
def test_a_name_that_only_python_would_strip_is_not_the_signed_in_reviewer(
    tmp_path: Path, disguised: str
) -> None:
    """The check normalises names as the record model stores them, not as str.strip does."""
    store, photo_id = store_with_photo(tmp_path)
    client, token = signed_in(tmp_path)
    body = {"status": "confirmed", "reviewer": disguised}
    response = client.post(f"/runs/run/photos/{photo_id}/review", json=body, headers=bearer(token))
    assert response.status_code == 403
    assert store.reviews("run", photo_id) == []


WRITES = [
    ("/runs/run/photos/p/review", "reviewer"),
    ("/runs/run/photos/p/audit", "reviewer"),
    ("/runs/run/photos/p/findings", "reviewer"),
    ("/runs/run/photos/p/judgements", "reviewer"),
    ("/runs/run/photos/p/leads", "selector"),
    ("/runs/run/photos/p/referrals", "referrer"),
    ("/runs/run/photos/p/referrals/1/events", "actor"),
    ("/studies", "author"),
    ("/studies/s/versions", "author"),
    ("/runs/run/study", "linked_by"),
]


@pytest.mark.parametrize(("path", "field"), WRITES)
def test_no_one_can_write_as_another_reviewer(tmp_path: Path, path: str, field: str) -> None:
    store, photo_id = store_with_photo(tmp_path)
    client, token = signed_in(tmp_path)
    path = path.replace("/p/", f"/{photo_id}/")
    body = {"status": "confirmed", field: "Ben"}
    response = client.post(path, json=body, headers=bearer(token))
    assert response.status_code == 403
    assert "Ana" in response.json()["detail"]
    assert store.reviews("run", photo_id) == []


def test_every_attributed_write_is_checked(tmp_path: Path) -> None:
    """A new attribution field on any write must be bound to the signed-in reviewer too."""
    attributed = {
        name
        for route in create_app(tmp_path).routes
        if isinstance(route, APIRoute) and route.methods == {"POST"} and route.body_field
        for name, field in typing.cast(
            typing.Any, route.body_field.field_info.annotation
        ).model_fields.items()
        if field.metadata == list(typing.get_args(ReviewerName)[1:])
    }
    assert attributed == ATTRIBUTION_FIELDS
    assert {field for _path, field in WRITES} == ATTRIBUTION_FIELDS


def test_session_names_the_mode_and_reviewer_but_never_the_token(tmp_path: Path) -> None:
    assert TestClient(create_app(tmp_path)).get("/session").json() == {"mode": "local"}
    client, token = signed_in(tmp_path)
    response = client.get("/session", headers=bearer(token))
    assert response.json() == {"mode": "tokens", "reviewer": "Ana"}
    assert token not in response.text


def test_tokens_mode_hides_the_interactive_docs(tmp_path: Path) -> None:
    client, _token = signed_in(tmp_path)
    assert client.get("/docs").status_code == 404
    assert client.get("/openapi.json").status_code == 404
    assert TestClient(create_app(tmp_path)).get("/docs").status_code == 200


def test_local_mode_needs_no_token(tmp_path: Path) -> None:
    _store, photo_id = store_with_photo(tmp_path)
    client = TestClient(create_app(tmp_path))
    body = {"status": "confirmed", "reviewer": "Ben"}
    assert client.post(f"/runs/run/photos/{photo_id}/review", json=body).status_code == 200


def test_tokens_are_never_logged(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.DEBUG)
    _store, photo_id = store_with_photo(tmp_path)
    client, token = signed_in(tmp_path)
    client.get("/runs", headers=bearer(token))
    client.get("/runs", headers=bearer(token + "x"))
    client.post(
        f"/runs/run/photos/{photo_id}/review",
        json={"status": "confirmed", "reviewer": "Ben"},
        headers=bearer(token),
    )
    secret = token.rsplit("_", 1)[-1]
    assert secret not in caplog.text
