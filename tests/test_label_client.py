"""Only required task metadata is read; REST credentials never enter result receipts."""

import json
import sqlite3

import pytest

from weedz.batches.label_client import task_index


def test_task_index_filters_project_and_keys_without_touching_annotations(tmp_path):
    path = tmp_path / "label.sqlite3"
    with sqlite3.connect(path) as db:
        db.executescript(
            "CREATE TABLE task(id INTEGER, project_id INTEGER, meta TEXT, data TEXT); "
            "CREATE TABLE annotation(result TEXT);"
        )
        db.execute("INSERT INTO annotation VALUES (?)", ("human",))
        for identifier, project, key in [(1, 1, "a"), (2, 1, "b"), (3, 2, "c")]:
            db.execute(
                "INSERT INTO task VALUES (?,?,?,?)",
                (
                    identifier,
                    project,
                    json.dumps({"external_id": key}),
                    json.dumps({"image": "exact"}),
                ),
            )
    before = path.read_bytes()
    assert task_index(path, 1, ["a"]) == {"a": {"id": 1, "data": {"image": "exact"}}}
    assert path.read_bytes() == before


def test_duplicate_external_identity_is_not_arbitrarily_overwritten(tmp_path):
    path = tmp_path / "label.sqlite3"
    with sqlite3.connect(path) as db:
        db.execute("CREATE TABLE task(id INTEGER, project_id INTEGER, meta TEXT, data TEXT)")
        for identifier in (1, 2):
            db.execute(
                "INSERT INTO task VALUES (?,1,?,?)", (identifier, '{"external_id":"same"}', "{}")
            )
    with pytest.raises(ValueError, match="Duplicate"):
        task_index(path, 1, ["same"])


def test_auth_refresh_does_not_reveal_token_or_response_body(tmp_path):
    import httpx

    from weedz.batches.label_client import LabelStudioClient

    path = tmp_path / "token"
    path.write_text("private-test-token")
    path.chmod(0o600)
    transport = httpx.MockTransport(
        lambda request: httpx.Response(403, json={"error": "private-test-token"})
    )
    with pytest.raises(RuntimeError) as caught:
        LabelStudioClient("http://127.0.0.1:8068", path, transport=transport)
    assert "private-test-token" not in str(caught.value)
    path.chmod(0o644)
    with pytest.raises(ValueError, match="owner-private"):
        LabelStudioClient("http://127.0.0.1:8068", path, transport=transport)
