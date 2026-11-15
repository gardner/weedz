"""Explicit connections and owned local Temporal evaluation-server configuration."""

import os
import re
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit

HOSTED_NAMESPACE = "weedz-hosted"
HOSTED_TASK_QUEUE = "weedz-hosted-discovery-v2"
_IDENTIFIER = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}")


@dataclass(frozen=True)
class TemporalConnection:
    address: str | None = None
    namespace: str = HOSTED_NAMESPACE
    task_queue: str = HOSTED_TASK_QUEUE
    tls: bool = False

    def __post_init__(self) -> None:
        if not _IDENTIFIER.fullmatch(self.namespace) or not _IDENTIFIER.fullmatch(self.task_queue):
            raise ValueError("Use explicit bounded Temporal namespace and task queue identifiers")
        if self.address is None:
            return
        try:
            parsed = urlsplit(f"//{self.address}")
            valid_address = (
                parsed.hostname
                and parsed.port
                and not parsed.username
                and not parsed.password
                and not parsed.path
                and not parsed.query
                and not parsed.fragment
            )
        except ValueError:
            valid_address = False
        if not valid_address:
            raise ValueError("Use a Temporal host:port without credentials, path or query")

    @property
    def target(self) -> str:
        return self.address or "127.0.0.1:7258"


def local_server_command(
    executable: Path,
    state: Path,
    port: int = 7258,
    namespace: str = HOSTED_NAMESPACE,
) -> list[str]:
    """Validate before any state is created; never download or search for a binary."""
    executable = executable.expanduser().resolve()
    if not executable.is_file() or not os.access(executable, os.X_OK):
        raise ValueError(
            "Provide an existing official Temporal CLI executable; no download is attempted"
        )
    if not 1024 <= port <= 65535:
        raise ValueError("Use an unprivileged local Temporal port")
    TemporalConnection(f"127.0.0.1:{port}", namespace=namespace)
    return [
        str(executable),
        "server",
        "start-dev",
        "--ip",
        "127.0.0.1",
        "--port",
        str(port),
        "--namespace",
        namespace,
        "--headless",
        "--db-filename",
        str(state.resolve() / "temporal.sqlite3"),
    ]
