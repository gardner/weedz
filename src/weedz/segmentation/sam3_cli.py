"""Explicit optional SAM3 runtime; the default discovery pipeline stays unchanged."""

import argparse
import json
import os
import tempfile
from pathlib import Path

from weedz.segmentation.artifacts import durable_mkdir, sync_directory
from weedz.segmentation.sam3_image import Sam3Config, Sam3Image


def _outside_git(path: Path) -> Path:
    resolved = path.resolve()
    if any((parent / ".git").exists() for parent in (resolved, *resolved.parents)):
        raise ValueError("SAM3 evidence/cache must remain outside Git")
    return resolved


def _publish(output: Path, result: dict) -> None:
    """Publish only complete durable bytes, without replacing concurrent evidence."""
    durable_mkdir(output.parent)
    with tempfile.NamedTemporaryFile(mode="w", dir=output.parent, delete=False) as stream:
        temporary = Path(stream.name)
        try:
            json.dump(result, stream, allow_nan=False)
            stream.flush()
            os.fsync(stream.fileno())
            os.link(temporary, output)
            sync_directory(output.parent)
        finally:
            temporary.unlink(missing_ok=True)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Pinned SAM3 still-image concept proposals")
    parser.add_argument("image", type=Path)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--cache", type=Path, required=True)
    parser.add_argument("--prompt", action="append", required=True)
    parser.add_argument("--threshold", type=float, default=0.5)
    parser.add_argument("--max-regions", type=int, default=128)
    parser.add_argument("--max-side", type=int, default=1024)
    parser.add_argument("--max-prompt-bytes", type=int, default=8_000_000)
    args = parser.parse_args(argv)
    output, cache = _outside_git(args.output), _outside_git(args.cache)
    if output.exists() or output.is_symlink():
        raise FileExistsError("Refusing to replace existing SAM3 evidence")
    config = Sam3Config(
        prompts=tuple(args.prompt),
        concept_threshold=args.threshold,
        max_regions=args.max_regions,
        max_prompt_bytes=args.max_prompt_bytes,
        max_side=args.max_side,
    )
    result = Sam3Image.load(args.checkpoint, config, cache).screen(args.image)
    _publish(output, result)
    print(
        json.dumps(
            {
                "output": str(output),
                "status": result["status"],
                "regions": len(result["regions"]),
                "model_version": result["model_version"],
            }
        )
    )
