"""Local authenticated REST access and a read-only, bounded task identity index."""

import json
import os
import sqlite3
import stat
from contextlib import closing
from pathlib import Path
from typing import Any

import httpx


def task_index(database: Path, project: int, keys: list[str]) -> dict[str, dict[str, Any]]:
    if not 1 <= len(keys) <= 1000 or type(project) is not int or project <= 0:
        raise ValueError("Choose a bounded task set and positive project ID")
    marks = ",".join("?" for _ in keys)
    query = (
        "SELECT id,meta,data FROM task WHERE project_id=? "
        f"AND json_extract(meta,'$.external_id') IN ({marks})"
    )
    with closing(sqlite3.connect(database.resolve().as_uri() + "?mode=ro", uri=True)) as db:
        rows = db.execute(query, [project, *keys]).fetchall()
    result = {}
    for identifier, raw_meta, raw_data in rows:
        key = json.loads(raw_meta)["external_id"]
        if key in result:
            raise ValueError("Duplicate external task identity")
        result[key] = {"id": identifier, "data": json.loads(raw_data)}
    return result


class LabelStudioClient(httpx.Client):
    def __init__(self, base_url: str, token_file: Path, **kwargs: Any) -> None:
        url = httpx.URL(base_url)
        if url.scheme != "http" or url.host not in {"127.0.0.1", "localhost", "::1"}:
            raise ValueError("Use the existing loopback Label Studio API")
        if url.username or url.password or url.query or url.fragment or url.path not in {"", "/"}:
            raise ValueError("Use a credential-free Label Studio API origin")
        self.token_file = token_file
        super().__init__(
            base_url=base_url, timeout=httpx.Timeout(30, connect=5, pool=5, write=10), **kwargs
        )
        try:
            self.refresh()
        except BaseException:
            self.close()
            raise

    def refresh(self) -> None:
        info = self.token_file.stat()
        if (
            self.token_file.is_symlink()
            or not stat.S_ISREG(info.st_mode)
            or info.st_uid != os.getuid()
            or info.st_mode & 0o077
            or info.st_size > 16_384
        ):
            raise ValueError("Use an owner-private Label Studio token file")
        token = self.token_file.read_text().strip()
        if not token:
            raise ValueError("Label Studio token file is empty")
        self.headers.pop("Authorization", None)
        response = super().request("POST", "/api/token/refresh/", json={"refresh": token})
        if not response.is_success:
            raise RuntimeError(f"Label Studio authentication failed ({response.status_code})")
        access = response.json().get("access")
        if not isinstance(access, str) or not access:
            raise RuntimeError("Label Studio returned no access credential")
        self.headers["Authorization"] = f"Bearer {access}"

    def request(self, method: str, url: Any, *args: Any, **kwargs: Any) -> httpx.Response:
        response = super().request(method, url, *args, **kwargs)
        if response.status_code == 401:
            self.refresh()
            response = super().request(method, url, *args, **kwargs)
        return response
