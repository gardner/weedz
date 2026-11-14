# Contributing to Weedz

Thank you for helping. Weedz is an open-source, non-commercial project for public
good. This guide explains how work is done here and how contributions are licensed.

## Set up

- Python: install [uv](https://docs.astral.sh/uv/). Run the project with
  `uv run main.py`, and add dependencies with `uv add <dependency>`, which picks
  the latest version.
- Web app: use `pnpm`, not `npm` (`pnpm --dir web install --frozen-lockfile`).
- Hooks: install the pre-commit hooks once per clone with
  `uv run pre-commit install`.

[README.md](README.md#run-it) explains how to run the local stack, and
[docs/local-development.md](docs/local-development.md) explains how it works.

## Code quality

The pre-commit hooks run the checks on every commit: Ruff lint and format,
McCabe complexity (8 at most), Pyright types, ShellCheck and a 500-line limit on
each source file. Let the hooks do this; do not bypass them. If a hook fails,
fix the cause and commit again.

Aim for code that is simple, readable and easy to maintain: strong types, small
functions, and names that say what things mean.

## Test first

Use test-driven development: **red, green, refactor.**

1. Write a failing test that describes the behaviour you want.
2. Write the simplest code that makes it pass.
3. Refactor while the tests stay green.

Tests use synthetic local data and must not need downloaded datasets or the
network. Run them with `uv run pytest`, and the web checks with
`pnpm --dir web check` and `pnpm --dir web test`.

## Issues, branches and pull requests

1. **Plan in the issue first.** Before picking up an issue, review it and the
   current code, and research anything uncertain. Then update the issue with a
   plain-language **The problem**, the proposed plan, and the other options
   considered.
2. **Branch per issue**, for example `feat/52-short-name` or `docs/32-licence`.
3. **Commit descriptively** at reasonable intervals.
4. **Open a pull request** that links the issue.
5. **Work through the review agents.** Automated reviewers (Claude, Z.ai, Codex
   and the quality checks) comment on each push. Wait until they have all
   finished before you push again. Then, for each comment:
   - if it is real, fix it in a new commit, reply with the commit SHA, and
     resolve the conversation;
   - if it is not relevant, reply saying why, and resolve it.

   `scripts/pr-review-threads.sh <owner/repo> <pr>` lists the open threads.
   Keep going until a round finds nothing relevant.
6. At the end of a large piece of work, review the whole change yourself and fix
   what you find.

## Data, photos and models

Respect the source terms. Photos, observations, datasets and model weights keep
their own licences; see [the README licence section](README.md#licence) and
[docs/datasets.md](docs/datasets.md#project-purpose-and-source-reuse). Do not
commit downloaded data, photos or weights. Do not add material whose licence
the sharing policy (`src/weedz/discovery/sharing.py`) does not admit. Never
include credentials or obscured locations.

## Licensing your contribution

Weedz is licensed under the [GNU General Public License v3.0 or later](LICENSE)
(`GPL-3.0-or-later`). Contributions use **inbound = outbound**: by contributing,
you license your contribution under those same terms. You keep your copyright,
and there is no contributor licence agreement.

Each commit must be signed off under the
[Developer Certificate of Origin 1.1](https://developercertificate.org/). The
sign-off certifies that you wrote the change, or otherwise have the right to
submit it under the project's licence. Add it with `git commit -s`, which
appends:

```text
Signed-off-by: Your Name <you@example.com>
```

Use your real name and an email address you can be reached at. If you forgot
to sign off, `git commit --amend -s` fixes the last commit, and
`git rebase --signoff origin/main` fixes a branch.
