"""Strict bounded RGB capture decoding: partial reads are valid, missing frames are not."""

import subprocess
from typing import BinaryIO

from PIL import Image


def read_exact(stream: BinaryIO, size: int) -> bytes:
    chunks = bytearray()
    while len(chunks) < size:
        chunk = stream.read(size - len(chunks))
        if not chunk:
            raise RuntimeError("Capture decoder ended early before a complete frame")
        chunks.extend(chunk)
    return bytes(chunks)


class CaptureDecoder:
    def __init__(self, command: list[str], size: tuple[int, int], frames: int, label: str):
        self.process = subprocess.Popen(command, stdout=subprocess.PIPE)
        self.size, self.expected, self.label = size, frames, label
        self.count = 0

    def frame(self) -> Image.Image:
        if self.count >= self.expected:
            raise RuntimeError(f"{self.label} requested too many capture frames")
        assert self.process.stdout is not None
        raw = read_exact(self.process.stdout, self.size[0] * self.size[1] * 3)
        self.count += 1
        if self.count == self.expected:
            if self.process.stdout.read(1):
                raise RuntimeError(f"{self.label} produced unexpected extra capture frames")
            code = self.process.wait(timeout=10)
            if code != 0:
                raise RuntimeError(f"{self.label} decoder exited with status {code}")
        return Image.frombytes("RGB", self.size, raw)

    def close(self, *, check: bool = True) -> None:
        # Termination is cleanup of an incomplete/failed render, never proof of decoding success.
        if self.process.poll() is None:
            self.process.terminate()
        if self.process.stdout is not None:
            self.process.stdout.close()
        try:
            code = self.process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            self.process.kill()
            code = self.process.wait(timeout=10)
        if check and (self.count != self.expected or code != 0):
            raise RuntimeError(f"{self.label} capture did not finish decoding successfully")
