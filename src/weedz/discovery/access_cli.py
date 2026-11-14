"""Invite and revoke remote reviewers: ``uv run main.py reviewers add|list|revoke``."""

import argparse
from pathlib import Path

from weedz.discovery.access import Access


def add(store: Access, args: argparse.Namespace) -> None:
    try:
        invite = store.invite(args.name)
    except ValueError as error:
        raise SystemExit(f"Not invited: {error}") from error
    print(
        f"Invited {invite.reviewer} (id {invite.id}). Send them this token privately; "
        "it is shown only now:\n\n"
        f"    {invite.token}\n\n"
        f"Revoke it with: uv run main.py reviewers revoke --id {invite.id}"
    )


def listing(store: Access, _args: argparse.Namespace) -> None:
    rows = store.reviewers()
    if not rows:
        print("No reviewers invited yet.")
    for row in rows:
        state = f"revoked {row['revoked_at'][:10]}" if row["revoked_at"] else "active"
        print(f"{row['id']:>4}  {row['reviewer']}  invited {row['created_at'][:10]}  {state}")


def revoke(store: Access, args: argparse.Namespace) -> None:
    if not store.revoke(args.id):
        raise SystemExit(f"No active invite with id {args.id}")
    print(f"Revoked invite {args.id}; it is refused from the next request.")


def parse(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="main.py reviewers", description="Invite tokens for remote reviewers"
    )
    commands = parser.add_subparsers(dest="command", required=True)
    invite = commands.add_parser("add", help="Invite a reviewer and print their token once")
    invite.add_argument("--name", required=True, help="Recorded with each of their records")
    commands.add_parser("list", help="Show invites, never their tokens")
    remove = commands.add_parser("revoke", help="Refuse an invite's token from now on")
    remove.add_argument("--id", type=int, required=True)
    for command in commands.choices.values():
        command.add_argument("--pilot-dir", type=Path, default=Path("data/pilot"))
    return parser.parse_args(argv)


def main(argv: list[str]) -> None:
    args = parse(argv)
    {"add": add, "list": listing, "revoke": revoke}[args.command](Access(args.pilot_dir), args)
