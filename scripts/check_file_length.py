"""Keep source modules small; usable as a pre-commit hook or standalone check."""

import argparse
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--max-lines", type=int, default=500)
    parser.add_argument("files", nargs="*", type=Path)
    args = parser.parse_args()
    paths = args.files or [
        Path("main.py"),
        *Path("src").rglob("*.py"),
        *Path("scripts").rglob("*.py"),
        *(
            path
            for folder in ["app", "components", "lib", "scripts"]
            for path in (Path("web") / folder).rglob("*")
            if path.suffix in {".ts", ".tsx", ".mjs", ".css"}
        ),
    ]
    failures = []
    for path in paths:
        count = len(path.read_text(encoding="utf-8").splitlines())
        if count > args.max_lines:
            failures.append(f"{path}: {count} lines (maximum {args.max_lines})")
    if failures:
        parser.exit(1, "\n".join(failures) + "\n")
    print(f"File length check passed ({len(paths)} files, maximum {args.max_lines} lines).")


if __name__ == "__main__":
    main()
