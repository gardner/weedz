"""Issue submitter tokens and serve report intake: ``uv run main.py intake ...`` (#57)."""

import argparse
import uuid
from pathlib import Path

from weedz.intake.submitters import Submitters


def add(args: argparse.Namespace) -> None:
    try:
        credential = Submitters(args.intake_dir).issue(args.label)
    except ValueError as error:
        raise SystemExit(f"Not issued: {error}") from error
    print(
        f"Issued submitter {credential.id} ({credential.label}). Put this token on that "
        "device privately; it is shown only now:\n\n"
        f"    {credential.token}\n\n"
        f"Revoke it with: uv run main.py intake revoke --id {credential.id}"
    )


def listing(args: argparse.Namespace) -> None:
    rows = Submitters(args.intake_dir).listing()
    if not rows:
        print("No submitters issued yet.")
    for row in rows:
        state = f"revoked {row['revoked_at'][:10]}" if row["revoked_at"] else "active"
        print(f"{row['id']:>4}  {row['label']}  issued {row['created_at'][:10]}  {state}")


def revoke(args: argparse.Namespace) -> None:
    if not Submitters(args.intake_dir).revoke(args.id):
        raise SystemExit(f"No active submitter with id {args.id}")
    print(f"Revoked submitter {args.id}; its reports are kept and it is refused from now on.")


def withdraw(args: argparse.Namespace) -> None:
    """For a person whose device token was lost or revoked, at their request."""
    from weedz.intake.store import ReportStore

    store, report_id = ReportStore(args.intake_dir), str(args.report)
    if store.receipt(args.submitter, report_id) is None:
        print(
            f"No report {report_id} yet; it is recorded as withdrawn, "
            "so it is refused if it arrives."
        )
    store.withdraw(args.submitter, report_id, before_arrival=True)
    print(f"Withdrew report {report_id}: any image is deleted and its content erased.")


def serve(args: argparse.Namespace) -> None:
    import uvicorn

    from weedz.intake.api import create_intake_app

    print(
        f"Report intake on http://{args.host}:{args.port}. Put it behind an HTTPS reverse "
        "proxy; devices send their token over that connection only.",
        flush=True,
    )
    # Uvicorn's access log has the method, path and status, never request headers.
    uvicorn.run(create_intake_app(args.intake_dir.resolve()), host=args.host, port=args.port)


def parse(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="main.py intake", description="Receive approved reports from devices"
    )
    commands = parser.add_subparsers(dest="command", required=True)
    issue = commands.add_parser("add", help="Issue a device token and print it once")
    issue.add_argument("--label", required=True, help="Your note of whose device it is")
    commands.add_parser("list", help="Show submitters, never their tokens")
    remove = commands.add_parser("revoke", help="Refuse a submitter's token from now on")
    remove.add_argument("--id", type=int, required=True)
    erase = commands.add_parser("withdraw", help="Withdraw a report for its submitter")
    erase.add_argument("--submitter", type=int, required=True)
    erase.add_argument("--report", type=uuid.UUID, required=True)
    run = commands.add_parser("serve", help="Serve the intake API")
    run.add_argument("--host", default="127.0.0.1", help="Loopback by default, for a proxy")
    run.add_argument("--port", type=int, default=8300)
    for command in commands.choices.values():
        command.add_argument("--intake-dir", type=Path, default=Path("data/intake"))
    return parser.parse_args(argv)


def main(argv: list[str]) -> None:
    args = parse(argv)
    commands = {"add": add, "list": listing, "revoke": revoke, "withdraw": withdraw, "serve": serve}
    commands[args.command](args)
