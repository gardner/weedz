# Package Managers

Use `uv run main.py`
Use `uv add <dependency>` to always get the latest version

Perfer `pnpm` instead of `npm` where possible.

# Static Code Analysis

To ensure code quality stays high and readable: Use strong types, code formatting, max-lines-per-file, and complexity detection. See: https://gist.github.com/gardner/22f2fb13cf2103f7a0197437dfa71bc8

## Workflow

- Make descriptive commits at reasonable intervals.
- Rely on the pre-commit hooks to run the checks, don't manually run the pre-commit checks. Ensure the pre-commit hooks are installed and working.
- Before picking up a GitHub Issue to work on: Review the issue, then review the existing code, then conduct any research to validate the contents of the issue or update the issue with a plan. Make sure to include a plain language explanation of "The Problem" that we're solving, the proposed plan to solve it, and any other options considered.
- When working on a GitHub Issue, create a new branch so we can submit a PR when it is ready.
- After submitting a PR, wait for the PR review agents to finish their review. Then if there are review comments use a subagent that:
    - If there are review comments then please evaluate if any of them are actually real or relevant, and then resolve the important issues with a new commit and resolve the GitHub PR conversation with information about the resolution, or with a comment saying why it is not relevant. After pushing a new commit, monitor the PR for new review comments and continue the process.
    - You can work on other things while waiting for the PR review comments.
    - After pushing wait for the code review agents to finish their review before pushing again.
      A pre-push hook enforces this: it refuses the push while `claude-review` or `zai-review` is still running on the branch's PR, because a new push cancels the running review. Wait with `gh pr checks <PR> --watch`. Install it with `uv run pre-commit install`. Push one branch at a time: pre-commit shows the hook only the first branch of a multi-branch push.
    - Keep looping like this until there are no more relevant issues found by the code review agents.
    - Then merge the PR.

# IMPORTANT

- Use TDD "Red, green, refactor" where possible. WRITE THE FAILING TESTS FIRST.
- Optimize for code readability and long-term maintenance.
- Write simple yet powerful code.
- Keep things elegant.
- Please make descriptive commits at reasonable intervals.
- Conduct a code review at the end of a large work slice and resolve any issues identified.
