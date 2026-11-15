"""Capture actual saved SAM2/BioCLIP evidence through the running production review UI."""

import argparse
import os
import subprocess
from pathlib import Path

from demo_paths import outside_git


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--web-url", default="http://127.0.0.1:3022")
    parser.add_argument("--ffmpeg", type=Path, required=True)
    args = parser.parse_args()
    output = outside_git(args.output)
    output.mkdir(parents=True, exist_ok=False)
    environment = os.environ | {
        "WEEDZ_CAPTURE_DIR": str(output),
        "WEEDZ_WEB_URL": args.web_url,
        "WEEDZ_FFMPEG": str(args.ffmpeg.resolve()),
    }
    subprocess.run(
        ["pnpm", "--dir", "web", "exec", "node", "scripts/capture-segmentation-ui.mjs"],
        cwd=Path(__file__).resolve().parents[1],
        env=environment,
        check=True,
    )


if __name__ == "__main__":
    main()
