"""Export a completed public experiment for Label Studio without changing human history."""

import argparse
import json
from pathlib import Path

from weedz.annotation.export import export_label_studio
from weedz.rights_profiles import PROFILES, PUBLIC_PROFILE


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--run", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--mode", choices=("assisted", "blind"), default="assisted")
    parser.add_argument("--image-prefix", default="corpus")
    parser.add_argument("--rights-profile", choices=tuple(PROFILES), default=PUBLIC_PROFILE)
    args = parser.parse_args()
    try:
        receipt = export_label_studio(
            args.source,
            args.run,
            args.output,
            mode=args.mode,
            image_prefix=args.image_prefix,
            rights_profile=args.rights_profile,
        )
    except ModuleNotFoundError as error:
        if error.name and error.name.startswith("label_studio_sdk"):
            parser.error("Mask export requires the optional SDK: uv sync --extra annotation")
        raise
    print(json.dumps({"output": str(args.output), "task_count": receipt["task_count"]}))


if __name__ == "__main__":
    main()
