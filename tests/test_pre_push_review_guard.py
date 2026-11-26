"""The pre-push hook refuses a push while a code review of the PR is still running."""

import json
import os
import subprocess
from pathlib import Path

HOOK = Path(__file__).resolve().parents[1] / "scripts" / "check-reviews-before-push.sh"

FAKE_GH = """#!/usr/bin/env bash
echo "$*" >> "$FAKE_LOG"
[[ -n "${FAKE_FAIL:-}" ]] && { echo "gh: network down" >&2; exit 1; }
case "$1 $2" in
  "pr list") printf '%s' "${FAKE_PR:-}" ;;
  "pr checks") printf '%s' "$FAKE_CHECKS"; exit "${FAKE_CHECKS_EXIT:-0}" ;;
esac
"""


def _check(name: str, bucket: str) -> dict:
    return {
        "name": name,
        "bucket": bucket,
        "startedAt": "2026-11-26T18:45:44Z",
        "link": f"https://github.com/gardner/weedz/actions/runs/1/job/{name}",
    }


def _push(tmp_path: Path, checks: list[dict] | None = None, **env: str):
    gh = tmp_path / "gh"
    gh.write_text(FAKE_GH)
    gh.chmod(0o755)
    environment = os.environ | {
        "GH": str(gh),
        "FAKE_LOG": str(tmp_path / "gh.log"),
        "FAKE_PR": "182",
        "FAKE_CHECKS": json.dumps(checks or []),
        "PRE_COMMIT_REMOTE_BRANCH": "refs/heads/feat/topic",
    }
    return subprocess.run(
        ["bash", str(HOOK)],
        env=environment | env,
        capture_output=True,
        text=True,
        cwd=tmp_path,
        check=False,
    )


def test_a_running_review_blocks_the_push_and_says_why(tmp_path: Path):
    checks = [_check("claude-review", "pass"), _check("zai-review", "pending")]
    result = _push(tmp_path, checks, FAKE_CHECKS_EXIT="8")
    assert result.returncode == 1
    message = result.stderr
    assert "zai-review" in message and "PR #182" in message
    assert "- zai-review" in message and "- claude-review" not in message
    assert "cancel an in-progress review" in message
    assert "gh pr checks 182 --watch" in message
    assert "scripts/pr-review-threads.sh" in message
    assert "--no-verify" in message


def test_finished_reviews_let_the_push_through(tmp_path: Path):
    checks = [_check("claude-review", "pass"), _check("zai-review", "fail")]
    assert _push(tmp_path, checks).returncode == 0


def test_other_running_checks_do_not_block(tmp_path: Path):
    checks = [_check("claude-review", "pass"), _check("python-quality", "pending")]
    assert _push(tmp_path, checks, FAKE_CHECKS_EXIT="8").returncode == 0


def test_a_branch_without_an_open_pr_pushes_freely(tmp_path: Path):
    result = _push(tmp_path, FAKE_PR="")
    assert result.returncode == 0
    assert "pr checks" not in (tmp_path / "gh.log").read_text()


def test_the_pr_is_looked_up_by_the_branch_being_pushed(tmp_path: Path):
    _push(tmp_path, [])
    assert "--head feat/topic" in (tmp_path / "gh.log").read_text()


def test_a_github_failure_warns_but_does_not_block(tmp_path: Path):
    result = _push(tmp_path, FAKE_FAIL="1")
    assert result.returncode == 0
    assert "couldn't check" in result.stderr


def test_without_pre_commit_it_uses_the_current_branch(tmp_path: Path):
    repo = tmp_path / "repo"
    subprocess.run(["git", "init", "-q", "-b", "work/current", str(repo)], check=True)
    gh = tmp_path / "gh"
    gh.write_text(FAKE_GH)
    gh.chmod(0o755)
    environment = {k: v for k, v in os.environ.items() if not k.startswith("PRE_COMMIT")}
    environment |= {"GH": str(gh), "FAKE_LOG": str(tmp_path / "gh.log"), "FAKE_PR": ""}
    subprocess.run(["bash", str(HOOK)], env=environment, cwd=repo, check=True)
    assert "--head work/current" in (tmp_path / "gh.log").read_text()


def test_a_failed_checks_lookup_warns_instead_of_passing_silently(tmp_path: Path):
    result = _push(tmp_path, FAKE_CHECKS="", FAKE_CHECKS_EXIT="1")
    assert result.returncode == 0
    assert "couldn't check" in result.stderr
