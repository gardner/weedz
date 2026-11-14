"""`weedz bundles`: make a signing key, build the text table, publish, verify and serve.

    weedz bundles keygen --key ~/.config/weedz/bundle.ed25519
    weedz bundles text-table --model bioclip-2 --out text.f32
    weedz bundles publish --spec bundle.json --key ~/.config/weedz/bundle.ed25519 --out site
    weedz bundles verify --out site --public-key <base64>
    weedz bundles serve --out site --port 8102

Paths in a bundle spec are relative to the spec file. Only public keys are ever printed.
"""

import argparse
import json
import logging
from datetime import UTC, datetime
from pathlib import Path

from weedz.bundles.manifest import BundleSpec, check_artefact, read_manifest
from weedz.bundles.publish import MANIFEST, artefact_path, publish
from weedz.bundles.signing import generate_key, key_id


def load_spec(path: Path) -> BundleSpec:
    raw = json.loads(path.read_text())
    base = path.resolve().parent
    raw["text_table"] = str(base / raw["text_table"])
    raw["image_model"]["path"] = str(base / raw["image_model"]["path"])
    raw["image_model"]["parity"]["benchmark"] = str(
        base / raw["image_model"]["parity"]["benchmark"]
    )
    return BundleSpec.model_validate(raw)


def _keygen(args: argparse.Namespace) -> None:
    public = generate_key(args.key)
    print(f"Wrote an owner-only private key to {args.key}; keep it off this repo and backed up.")
    print(f"public key (pin this in the app): {public}")
    print(f"key id: {key_id(public)}")


def _publish(args: argparse.Namespace) -> None:
    public = publish(load_spec(args.spec), args.key, args.out)
    print(f"Published {args.out / MANIFEST}, verifiable with public key {public}")


def _verify(args: argparse.Namespace) -> None:
    envelope = json.loads((args.out / MANIFEST).read_text())
    manifest = read_manifest(
        envelope,
        args.public_key,
        today=datetime.now(UTC).date(),
        installed=0,
        app_version=args.app_version,
    )
    for part in ("image_model", "text_table"):
        check_artefact(artefact_path(args.out, manifest[part]["sha256"]), manifest[part])
    print(f"Bundle {manifest['sequence']} verified: signature, expiry and artefact hashes")


def _text_table(args: argparse.Namespace) -> None:  # pragma: no cover - loads a model
    from weedz.bundles.text_table import write_text_table

    entry = write_text_table(args.model, args.out)
    print(f"Wrote {args.out}: shape {entry['shape']}, sha256 {entry['sha256']}")


def _serve(args: argparse.Namespace) -> None:  # pragma: no cover - runs a server
    import uvicorn

    from weedz.bundles.api import create_app

    uvicorn.run(create_app(args.out), host=args.host, port=args.port)


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(
        prog="weedz bundles",
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    commands = root.add_subparsers(dest="command", required=True)
    keygen = commands.add_parser("keygen", help="Write a new Ed25519 signing key")
    keygen.add_argument("--key", type=Path, required=True)
    keygen.set_defaults(run=_keygen)
    table = commands.add_parser("text-table", help="Embed the fixed prompts (loads the model)")
    table.add_argument("--model", choices=("bioclip", "bioclip-2"), default="bioclip-2")
    table.add_argument("--out", type=Path, required=True)
    table.set_defaults(run=_text_table)
    pub = commands.add_parser("publish", help="Sign and publish a bundle into a static tree")
    pub.add_argument("--spec", type=Path, required=True)
    pub.add_argument("--key", type=Path, required=True)
    pub.add_argument("--out", type=Path, required=True)
    pub.set_defaults(run=_publish)
    check = commands.add_parser("verify", help="Check a published tree as a device would")
    check.add_argument("--out", type=Path, required=True)
    check.add_argument("--public-key", action="append", required=True)
    check.add_argument("--app-version", default="999.0.0")
    check.set_defaults(run=_verify)
    serve = commands.add_parser("serve", help="Serve a published tree for development")
    serve.add_argument("--out", type=Path, required=True)
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8102)
    serve.set_defaults(run=_serve)
    return root


def main(argv: list[str] | None = None) -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    args = parser().parse_args(argv)
    try:
        args.run(args)
    except (OSError, ValueError) as error:
        raise SystemExit(f"weedz bundles: {error}") from error
