"""Checksummed request cache and polite read-only HTTP acquisition."""

import hashlib
import json
import time
from pathlib import Path
from typing import Any

import httpx


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False))
    temporary.replace(path)


class Acquisition:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.client = httpx.Client(
            timeout=90, follow_redirects=True, headers={"User-Agent": "GreatWalksFungiResearch/1.0"}
        )
        self.last_inat = 0.0
        self.receipts: list[dict[str, Any]] = []

    def json(self, url: str, params: dict[str, Any]) -> dict[str, Any]:
        identity = hashlib.sha256(json.dumps([url, params], sort_keys=True).encode()).hexdigest()
        path = self.root / (identity + ".json")
        receipt = path.with_suffix(".receipt.json")
        if path.exists() and receipt.exists():
            expected = json.loads(receipt.read_text())
            if (
                sha(path) != expected["sha256"]
                or expected["url"] != url
                or expected["params"] != params
            ):
                raise ValueError(f"Cached reply checksum mismatch: {path}")
            self.receipts.append(expected)
            return json.loads(path.read_text())
        data = self._fetch(url, params)
        write_json(path, data)
        evidence = {
            "url": url,
            "params": params,
            "sha256": sha(path),
            "retrieved_unix": time.time(),
            "file": path.name,
        }
        write_json(receipt, evidence)
        self.receipts.append(evidence)
        return data

    def _fetch(self, url: str, params: dict[str, Any]) -> dict[str, Any]:
        for attempt in range(6):
            if "inaturalist.org" in url:
                time.sleep(max(0, 1.1 - (time.monotonic() - self.last_inat)))
                self.last_inat = time.monotonic()
            try:
                response = self.client.get(url, params=params)
                if response.status_code in (429, 500, 502, 503, 504):
                    time.sleep(min(60, 2**attempt * 3))
                    continue
                response.raise_for_status()
                data = response.json()
                if data.get("error"):
                    raise ValueError(f"Source API error: {data['error']}")
                return data
            except (httpx.TimeoutException, httpx.NetworkError):
                time.sleep(min(60, 2**attempt * 3))
        raise RuntimeError(f"Acquisition failed after retries: {url}")
