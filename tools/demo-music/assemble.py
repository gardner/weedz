"""Join original Music3 passages into a documented bed; never touch narration."""

import argparse
import hashlib
import json
import math
from pathlib import Path

import numpy as np
from numpy.typing import NDArray

Audio = NDArray[np.float32]
ROOT = Path(__file__).resolve().parents[2]


def frames(rate: int, seconds: float) -> int:
    if rate <= 0 or not math.isfinite(seconds) or seconds < 0:
        raise ValueError("Sample rate must be positive and duration finite/nonnegative")
    return round(rate * seconds)


def validate_audio(audio: Audio) -> None:
    if audio.ndim != 2 or audio.shape[1] != 2 or not np.isfinite(audio).all():
        raise ValueError("Music must be finite stereo audio")


def crossfade(pieces: list[Audio], rate: int, seconds: float) -> Audio:
    if not pieces:
        raise ValueError("Provide original music passages")
    overlap = frames(rate, seconds)
    for piece in pieces:
        validate_audio(piece)
    if not overlap:
        return np.concatenate(pieces)
    result = pieces[0].copy()
    ramp = np.linspace(0, 1, overlap, dtype=np.float32)[:, None]
    for piece in pieces[1:]:
        if min(len(result), len(piece)) < overlap:
            raise ValueError("A source is shorter than the crossfade")
        blend = result[-overlap:] * (1 - ramp) + piece[:overlap] * ramp
        result = np.concatenate((result[:-overlap], blend, piece[overlap:]))
    return result


def trim_and_fade(
    audio: Audio, rate: int, seconds: float, fade_in: float, fade_out: float
) -> Audio:
    validate_audio(audio)
    count, intro, outro = frames(rate, seconds), frames(rate, fade_in), frames(rate, fade_out)
    if len(audio) < count:
        raise ValueError("Insufficient original material; no looping or silence padding is used")
    if not count or intro + outro > count:
        raise ValueError("Fades must fit inside a nonempty target")
    result = audio[:count].copy()
    if intro:
        result[:intro] *= np.linspace(0, 1, intro, dtype=np.float32)[:, None]
    if outro:
        result[-outro:] *= np.linspace(1, 0, outro, dtype=np.float32)[:, None]
    return result


def assemble(args: argparse.Namespace) -> None:
    import soundfile as sf

    output = args.output.resolve()
    manifest = output.with_suffix(".assembly.json")
    if output.is_relative_to(ROOT) or output.exists() or manifest.exists():
        raise ValueError("Use a new output outside the repository; existing files are preserved")
    pieces, sources, rate = [], [], None
    for source in args.inputs:
        provenance = json.loads(source.with_suffix(".json").read_text())
        if provenance.get("model") != "MiniMaxAI/MiniMax-Music3":
            raise ValueError("Only Music3 source passages may enter this music-only assembly")
        audio, source_rate = sf.read(source, dtype="float32", always_2d=True)
        if rate is not None and rate != source_rate:
            raise ValueError(
                "Source rates differ; resampling must be an explicit separate operation"
            )
        rate = source_rate
        pieces.append(audio)
        sources.append(
            {
                "file": str(source.resolve()),
                "sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
                "frames": len(audio),
                "seconds": len(audio) / rate,
                "generation_provenance": str(source.with_suffix(".json").resolve()),
            }
        )
    assert rate is not None
    joined = crossfade(pieces, rate, args.crossfade)
    result = trim_and_fade(joined, rate, args.seconds, args.fade_in, args.fade_out)
    output.parent.mkdir(parents=True, exist_ok=True)
    sf.write(output, result, rate, subtype="PCM_16")
    record = {
        "machine_generated": True,
        "sources": sources,
        "sample_rate": rate,
        "channels": 2,
        "frames": len(result),
        "seconds": len(result) / rate,
        "linear_crossfade_seconds": args.crossfade,
        "fade_in_seconds": args.fade_in,
        "fade_out_seconds": args.fade_out,
        "trimmed_seconds": (len(joined) - len(result)) / rate,
        "normalization": "none",
        "looping": False,
        "narration_modified": False,
        "peak": float(np.max(np.abs(result))),
        "rms": float(np.sqrt(np.mean(result**2))),
        "output": str(output),
        "sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
    }
    manifest.write_text(json.dumps(record, indent=2) + "\n")
    print(json.dumps(record, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("inputs", type=Path, nargs="+")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--seconds", type=float, default=180)
    parser.add_argument("--crossfade", type=float, default=4)
    parser.add_argument("--fade-in", type=float, default=2)
    parser.add_argument("--fade-out", type=float, default=4)
    assemble(parser.parse_args())


if __name__ == "__main__":
    main()
