"""Hosted connections and explicit overrides are validated before mutating server state."""

import pytest

from weedz.discovery.hosting import TemporalConnection, local_server_command


def test_external_service_connection_does_not_require_a_local_binary():
    connection = TemporalConnection(
        address="temporal.example.org:7233", namespace="weedz-hosted", tls=True
    )
    assert connection.address == "temporal.example.org:7233"
    assert connection.namespace == "weedz-hosted"
    assert connection.task_queue == "weedz-hosted-discovery-v2"


def test_missing_local_executable_fails_before_creating_persistent_state(tmp_path):
    state = tmp_path / "not-created"
    with pytest.raises(ValueError, match="existing.*Temporal.*executable"):
        local_server_command(tmp_path / "missing", state)
    assert not state.exists()


def test_nonexecutable_file_is_not_accepted_as_a_server(tmp_path):
    executable = tmp_path / "temporal"
    executable.write_text("not an executable")
    executable.chmod(0o600)
    with pytest.raises(ValueError, match="executable"):
        local_server_command(executable, tmp_path / "state")
    assert not (tmp_path / "state").exists()


def test_owned_local_server_has_private_persistence_and_no_public_ui(tmp_path):
    executable = tmp_path / "temporal"
    executable.write_text("#!/bin/sh\nexit 0\n")
    executable.chmod(0o700)
    state = tmp_path / "state"
    command = local_server_command(executable, state)
    assert command[:3] == [str(executable), "server", "start-dev"]
    assert command[command.index("--ip") + 1] == "127.0.0.1"
    assert command[command.index("--namespace") + 1] == "weedz-hosted"
    assert command[command.index("--db-filename") + 1] == str(state / "temporal.sqlite3")
    assert "--headless" in command
    assert not state.exists()


@pytest.mark.parametrize("address", ["user:secret@host:7233", "https://host:7233", "host:99999"])
def test_connection_rejects_ambiguous_or_secret_bearing_addresses(address):
    with pytest.raises(ValueError):
        TemporalConnection(address=address, namespace="weedz-hosted", tls=True)
