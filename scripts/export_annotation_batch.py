"""Export a canonical batch with separate editable model prediction versions."""

import argparse
import json
from pathlib import Path

from weedz.annotation.samples import export_samples
from weedz.rights_profiles import PROFILES, PUBLIC_PROFILE


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--frame-results", type=Path)
    parser.add_argument("--proposals", type=Path)
    parser.add_argument("--regional-results", type=Path)
    parser.add_argument("--tiled-results", type=Path)
    parser.add_argument("--image-prefix", default="corpus")
    parser.add_argument("--rights-profile", choices=tuple(PROFILES), default=PUBLIC_PROFILE)
    args = parser.parse_args()
    result = export_samples(
        args.manifest,
        args.output,
        frame_results=args.frame_results,
        proposals=args.proposals,
        regional_results=args.regional_results,
        tiled_results=args.tiled_results,
        image_prefix=args.image_prefix,
        rights_profile=args.rights_profile,
    )
    print(json.dumps({"output": str(args.output), "task_count": result["task_count"]}))


if __name__ == "__main__":
    main()
