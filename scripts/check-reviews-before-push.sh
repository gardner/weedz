#!/usr/bin/env bash
# Pre-push hook: refuse a push while a code review of the branch's PR is running.
#
# The review workflows cancel an in-progress run when a new commit arrives
# (concurrency: cancel-in-progress), so pushing mid-review throws that review
# away and starts again from scratch. GLM reviews often take 10-30 minutes,
# so repeated pushes can mean it never finishes.
#
# Fails open: if gh or jq is missing, or GitHub can't be reached, it warns and
# lets the push through. `git push --no-verify` skips it for urgent fixes.
#
# One branch per push: pre-commit passes only the first pushed ref to the hook
# (PRE_COMMIT_REMOTE_BRANCH), so `git push --all` or several refspecs at once
# checks only the first branch. Push branches one at a time.
set -uo pipefail

gh_cli="${GH:-gh}"
review_checks="${REVIEW_CHECKS:-claude-review zai-review}"

warn() { echo "pre-push: couldn't check for running reviews ($1); pushing anyway." >&2; }

branch="${PRE_COMMIT_REMOTE_BRANCH:-$(git symbolic-ref --quiet HEAD 2>/dev/null)}"
branch="${branch#refs/heads/}"
[[ -n "$branch" ]] || exit 0
command -v jq >/dev/null || { warn "jq is not installed"; exit 0; }

if ! pr="$("$gh_cli" pr list --head "$branch" --state open --json number --jq '.[0].number // empty' 2>/dev/null)"; then
  warn "gh pr list failed"
  exit 0
fi
[[ -n "$pr" ]] || exit 0

# gh exits 8 when any check is pending; the JSON is still complete then.
checks="$("$gh_cli" pr checks "$pr" --json name,bucket,startedAt,link 2>/dev/null)"
status=$?
if [[ $status -ne 0 && $status -ne 8 ]]; then
  warn "gh pr checks failed with status $status"
  exit 0
fi
if ! running="$(jq -r --arg names "$review_checks" '
    ($names | split(" ")) as $reviews
    | .[] | select(.bucket == "pending" and (.name as $n | $reviews | index($n)))
    | "  - \(.name) (started \(.startedAt)): \(.link)"' <<<"$checks" 2>/dev/null)"; then
  warn "unexpected gh pr checks output"
  exit 0
fi
[[ -n "$running" ]] || exit 0
repo="$("$gh_cli" repo view --json nameWithOwner --jq .nameWithOwner 2>/dev/null)"

cat >&2 <<EOF
pre-push: push refused. A code review of PR #$pr is still running:

$running

Why: the review workflows cancel an in-progress review when a new commit is
pushed. Pushing now throws this review away, and the next one starts again
from scratch, so its findings never arrive. GLM reviews often take 10-30
minutes; repeated pushes can mean it never finishes.

What to do:
  1. Wait for the reviews to finish:  gh pr checks $pr --watch
  2. Read their findings:             bash scripts/pr-review-threads.sh ${repo:-<owner/repo>} $pr
  3. Fix what's real, reply to and resolve each thread, then push once,
     with everything in it.

Urgent fix that can't wait? git push --no-verify skips this check.
EOF
exit 1
