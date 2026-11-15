"""A listening Temporal server alone must not advertise a ready hosted worker."""

import json

from weedz.discovery.hosting import TemporalConnection
from weedz.discovery.workflow_health import (
    clear_worker_health,
    publish_worker_health,
    worker_is_ready,
)


def test_only_a_fresh_matching_live_worker_is_ready(tmp_path):
    path = tmp_path / "private/worker.json"
    connection = TemporalConnection()
    assert not worker_is_ready(path, connection, now=100)
    publish_worker_health(path, connection, "owned-worker", now=100)
    assert worker_is_ready(path, connection, now=105)
    assert not worker_is_ready(path, connection, now=130)
    assert not worker_is_ready(path, TemporalConnection(namespace="another-project"), now=105)
    assert not worker_is_ready(path, TemporalConnection(task_queue="another-queue"), now=105)
    assert path.stat().st_mode & 0o077 == 0
    assert path.parent.stat().st_mode & 0o077 == 0


def test_future_malformed_or_dead_worker_markers_fail_closed(tmp_path):
    path = tmp_path / "private/worker.json"
    connection = TemporalConnection()
    publish_worker_health(path, connection, "owned-worker", now=100)
    assert not worker_is_ready(path, connection, now=90)
    record = json.loads(path.read_text())
    record["pid"] = 2**31 - 1
    path.write_text(json.dumps(record))
    assert not worker_is_ready(path, connection, now=105)
    path.write_text("not JSON")
    assert not worker_is_ready(path, connection, now=105)


def test_old_worker_shutdown_cannot_remove_a_replacement_marker(tmp_path):
    path = tmp_path / "private/worker.json"
    connection = TemporalConnection()
    publish_worker_health(path, connection, "replacement", now=100)
    clear_worker_health(path, "old-worker")
    assert worker_is_ready(path, connection, now=105)
    clear_worker_health(path, "replacement")
    assert not path.exists()
