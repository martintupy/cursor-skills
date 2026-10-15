---
name: pull-request
description: Create or update a pull request with a Conventional Commits title and a structured description.
disable-model-invocation: true
compatibility: Requires git and an authenticated GitHub CLI (gh)
---

# Creating a PR

## 1. Gather context

Run `scripts/gather-context.sh [base]` from the skill root. The diff covers only this branch's work since the merge base, including uncommitted changes to tracked files. Untracked files (`??` in STATUS) are not in the diff — read them directly if they belong to the PR.

## 2. Self-review

Check the added lines of the diff for:

- Secrets, credentials, or `.env` values — abort and warn the user
- Debug statements (`print(`, `console.log`, `debugger`) outside `cli/` and `scripts/` — abort and warn the user
- Unrelated changes — ask with `AskQuestion` whether to split them into separate PRs, include everything in one PR, or leave the unrelated files uncommitted

When splitting, run the remaining steps once per PR, staging only that PR's files.

Find the repository's lint check and fix commands in `AGENTS.md`, `CLAUDE.md`, the `Makefile` or `.pre-commit-config.yaml` (e.g. `make lint-check` / `make lint-fix` in datamap, `uv run pre-commit run --all-files` in jarvis_core). If none exists, skip linting and say so.

Run the check. If it fails, run the fix, then the check again, and fix what remains by hand in this PR's files. Fix commands usually run repo-wide, so afterwards:

- Keep fixes only in files this PR touches
- Revert fixes in other files that were clean in STATUS with `git checkout -- <path>`; never revert files that already had uncommitted changes
- If failures remain only in files outside this PR, report them to the user and continue instead of blocking the PR

## 3. Check for issue references

Scan the branch name and commit messages for Jira keys of the known projects `SUP` and `SK`, case-insensitively (`(SUP|SK)-\d+`), and normalize to uppercase (`martin-sup-304-access-control` → `SUP-304`). If found, use it without prompting. Other `WORD-123` tokens like `GPT-6` or `UTF-8` are not Jira keys, and neither are GitHub references like `#123`.

If not found, ask with `AskQuestion` whether to link one, with options "No linked issue" and "I'll type the key or link" (entered via Other). Accept a bare key or a Jira URL (`https://dius-team.atlassian.net/browse/SUP-330` → `SUP-330`).

## 4. Ensure a feature branch

If BRANCH equals DEFAULT_BRANCH, create a branch before committing:

- With a Jira key: `<KEY>-<short-kebab-summary>` (e.g. `SUP-330-remove-for-mining`)
- Without: `<type>/<short-kebab-summary>` (e.g. `chore/pull-request-skill`)

When splitting into multiple PRs, branch each one from the up-to-date base, not from the previous PR's branch.

## 5. Generate title and description

**Title** — [Conventional Commits](https://www.conventionalcommits.org/en/v1.0.0/) format: `<type>(<optional-scope>)<optional-!>: <description>`

- Types follow [`@commitlint/config-conventional`](https://github.com/conventional-changelog/commitlint/tree/master/%40commitlint/config-conventional) — nothing else (no `cicd`, `update`, `wip`). Pick the type of the dominant change:
  - `feat`: a new feature
  - `fix`: a bug fix
  - `docs`: documentation only
  - `style`: formatting with no change in meaning
  - `refactor`: a code change that neither fixes a bug nor adds a feature
  - `perf`: a performance improvement
  - `test`: adding or correcting tests
  - `build`: build system or dependencies
  - `ci`: CI configuration and scripts
  - `chore`: other changes that don't modify `src/` or `tests/`
  - `revert`: reverts a previous commit
- Use a scope when the change sits in one area, matching existing commits (e.g. `refactor(agentic-search): ...`)
- Add `!` before the colon whenever there is a Breaking Changes section (e.g. `refactor(schema)!: remove for_mining option`)
- Description: English, imperative mood, lowercase first letter, no trailing period, one space after the colon
- Whole title at most 100 characters

**Description** — using this exact structure, omitting the Jira line when there is no key:

```markdown
## Summary

<one sentence: what this PR does concretely>

Jira: [SUP-123](https://dius-team.atlassian.net/browse/SUP-123)

## Changes

- <bullet 1>
- <bullet 2>

## Breaking Changes (only if applicable)

- <what changed for clients and what they must do>
```

- One bullet per feature/capability, not per file, under 15 words
- Use "Add", "Fix", "Improve", "Refactor", "Remove" as bullet prefixes
- Summary must name specific features/endpoints — no filler phrases
- Add "Breaking Changes" when removing or renaming request/response fields, endpoints, or env vars, or when changing behavior existing clients rely on. If unsure whether anything still depends on the change, ask the user.

## 6. Commit, push, and create/update

If STATUS shows changes belonging to this PR, stage them by explicit path (never `git add -A` when the tree contains unrelated changes) and commit with the generated title as message.

Never add AI attribution: no `Co-authored-by` trailer in commits, no "Made with Cursor" or similar footer in the PR body. After committing, check `git log -1 --format=%B`; if a trailer was added, amend it away and tell the user to disable Cursor Settings → Attribution.

If any existing subject in COMMITS does not follow Conventional Commits, list those commits and tell the user to squash-merge the PR so only the title lands on the base branch. Never rewrite already-pushed commits on your own.

Push with `git push -u origin HEAD`, then:

- New PR: `gh pr create --base <base> --title "<title>" --body "$(cat <<'EOF' ... EOF)"`
- Existing PR: the new body replaces the old one entirely. Keep any content in the existing body outside the generated sections (screenshots, reviewer notes, checklists) below the Changes section, show the proposed title and body, and confirm with `AskQuestion` before running `gh pr edit`.

Present the final title, description, and PR link in the response.

## Examples

Good:

```markdown
feat: add implicit read access for datamap-admin on system object instances

## Summary

Grant datamap-admin implicit read access to SYSTEM_OBJECT instances without requiring explicit permission grants.

## Changes

- Add admin bypass clause to instance visibility query for SYSTEM_OBJECT schemas
- Fetch system object schema IDs when user has datamap-admin role
- Add integration tests for admin implicit read and permission isolation
```

Bad:

```markdown
refactor: improve service layer

## Summary

This PR improves the overall developer experience by streamlining the service layer.

## Changes

- Refactor instance_service.py
- Update instance_repository.py
- Fix various issues
```
