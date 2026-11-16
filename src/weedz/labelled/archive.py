"""Read SHA-pinned archives in place; publisher paths never reach extraction APIs."""

import hashlib
import stat
import tarfile
import zipfile
from pathlib import Path, PurePosixPath
from types import TracebackType
from typing import BinaryIO


class SourceArchive:
    """A single open descriptor binds verification and all subsequent member reads."""

    def __init__(self, path: Path, sha256: str, *, maximum_members: int = 2000):
        self.path = path
        self.sha256 = sha256
        self.maximum_members = maximum_members
        self.stream: BinaryIO | None = None
        self.container: zipfile.ZipFile | tarfile.TarFile | None = None
        self.members: dict[str, zipfile.ZipInfo | tarfile.TarInfo] = {}

    def __enter__(self) -> "SourceArchive":
        self.stream = self.path.open("rb")
        try:
            self.verify()
            if zipfile.is_zipfile(self.stream):
                self.container = zipfile.ZipFile(self.stream)
                entries = self.container.infolist()
            else:
                self.stream.seek(0)
                self.container = tarfile.open(fileobj=self.stream, mode="r:*")
                entries = self.container.getmembers()
            self._index(entries)
            return self
        except BaseException:
            self.__exit__(None, None, None)
            raise

    def _index(self, entries: list) -> None:
        if len(entries) > self.maximum_members:
            raise ValueError("Archive member budget exceeded")
        for entry in entries:
            name = entry.orig_filename if isinstance(entry, zipfile.ZipInfo) else entry.name
            if isinstance(entry, zipfile.ZipInfo) and entry.filename != entry.orig_filename:
                raise ValueError("Unsafe normalized archive member name")
            parts = PurePosixPath(name).parts
            if "\\" in name or "\x00" in name or name.startswith("/") or ".." in parts:
                raise ValueError(f"Unsafe archive member: {name!r}")
            if name in self.members:
                raise ValueError(f"Duplicate archive member: {name}")
            if not self._directory(entry):
                self.members[name] = entry

    @staticmethod
    def _directory(entry: zipfile.ZipInfo | tarfile.TarInfo) -> bool:
        if isinstance(entry, zipfile.ZipInfo):
            if stat.S_ISLNK(entry.external_attr >> 16) or entry.flag_bits & 1:
                raise ValueError("Unsafe symlink or encrypted archive member")
            return entry.is_dir()
        if not (entry.isfile() or entry.isdir()):
            raise ValueError("Unsafe non-regular archive member")
        return entry.isdir()

    def verify(self) -> None:
        if self.stream is None:
            raise RuntimeError("Archive is not open")
        self.stream.seek(0)
        checksum = hashlib.sha256()
        while chunk := self.stream.read(1024 * 1024):
            checksum.update(chunk)
        if checksum.hexdigest() != self.sha256:
            raise ValueError("Source archive checksum mismatch")
        self.stream.seek(0)

    def read(self, name: str, *, maximum_bytes: int = 64_000_000) -> bytes:
        entry = self.members[name]
        size = entry.file_size if isinstance(entry, zipfile.ZipInfo) else entry.size
        if size > maximum_bytes:
            raise ValueError("Archive member byte budget exceeded")
        if isinstance(self.container, zipfile.ZipFile) and isinstance(entry, zipfile.ZipInfo):
            stream = self.container.open(entry)
        elif isinstance(self.container, tarfile.TarFile) and isinstance(entry, tarfile.TarInfo):
            stream = self.container.extractfile(entry)
        else:
            raise RuntimeError("Archive is not open")
        if stream is None:
            raise ValueError("Missing regular member")
        with stream:
            raw = stream.read(maximum_bytes + 1)
        if len(raw) != size:
            raise ValueError("Archive member size mismatch")
        return raw

    def __exit__(
        self,
        kind: type[BaseException] | None,
        error: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        if self.container is not None:
            self.container.close()
        if self.stream is not None:
            self.stream.close()
