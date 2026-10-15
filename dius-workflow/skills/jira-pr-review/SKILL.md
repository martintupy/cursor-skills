---
name: jira-pr-review
description: >-
  Fetch Jira work items with the acli CLI and GitHub pull requests with the gh CLI, and review all
  PRs linked to a Jira ticket across Dius-ai repositories. Use when the user mentions a Jira key
  (SUP-123, SK-45) or a dius-team.atlassian.net URL, asks about a ticket's status, description or
  comments, or asks to find, list, or review PRs for a ticket.
---

# Jira + GitHub PR Review

## Tools

Both CLIs are installed and authenticated. Use them instead of WebFetch, which cannot pass Jira auth.

Accept a bare key or a URL: `https://dius-team.atlassian.net/browse/SUP-335` → `SUP-335`.

### Jira (`acli`)

```bash
acli jira workitem view SUP-335 --fields summary,status,assignee,description,comment --json
acli jira workitem comment list --key SUP-335 --json --paginate
acli jira workitem search --jql 'parent = SUP-335' --fields key,summary,status --json
acli jira workitem search --jql 'project = SUP AND assignee = currentUser() AND statusCategory != Done' --json
```

`acli` cannot read the Jira development panel, so PR links must be found through `gh`.

Read-only by default. Never run `create`, `edit`, `transition`, `assign`, `comment create` or `delete` without explicit user confirmation.

### GitHub (`gh`)

```bash
gh search prs "SUP-335" --owner Dius-ai --state open --json number,title,url,repository,author
gh pr view <n> -R Dius-ai/<repo> --json title,body,baseRefName,headRefName,files,reviewDecision,statusCheckRollup,comments,reviews
gh pr diff <n> -R Dius-ai/<repo> --name-only
gh pr checks <n> -R Dius-ai/<repo>
```

- `gh pr list --json` has no `repository` field; use `gh search prs` for cross-repo lookups.
- On zsh, `for r in "a 1"; do set -- $r` does not word-split. Iterate over `repo/number` strings and split with `${pr%/*}` and `${pr#*/}`.
- `gh pr diff` output is truncated in tool results for large PRs. Read full files at the PR head instead:
  `git -C <clone> fetch -q origin <headRefName> && git -C <clone> show FETCH_HEAD:<path>`

Other Dius-ai repositories are usually cloned as siblings of the current repository (`../datamap`, `../dataapi`, `../jarvis_core`, ...). Use them to read code the diff touches but does not show. If a clone is missing, read files with `gh api repos/Dius-ai/<repo>/contents/<path>?ref=<headRefName> -H "Accept: application/vnd.github.raw"`.

## Reviewing a ticket's PRs

1. **Ticket**: fetch summary, description, comments and subtasks. Extract the acceptance criteria.
2. **Find PRs**: `gh search prs "<KEY>" --owner Dius-ai --state open`. If nothing is found, also try `--state all` and tell the user, since PRs without the key in title, body or branch are missed.
3. **Metadata**: for each PR, get body, files, CI status and existing reviews. Do not repeat points existing reviewers already raised.
4. **Read the code**: get the full diff per PR. For each change, read the callers and helpers it relies on in the local clone. Never assume what a helper does.
5. **Cross-PR consistency**: when PRs span repos, check that:
   - field names, enums and contracts match on both sides (client schema vs server model, prompt text vs accepted filters)
   - the rollout order in the PR bodies is actually required and sufficient
   - anything one PR depends on but no PR delivers is flagged
6. **Against the ticket**: check whether the PRs together satisfy the acceptance criteria, and what is missing or out of scope.

Review checklist per PR:
- Correctness and edge cases (empty values, missing keys, type mismatches such as UUID vs str dict keys)
- Silent failures or swallowed errors
- Tests that actually cover the new behaviour, including the negative path
- Migration or one-off scripts: idempotency, dry-run, pagination of list calls, fields dropped on update
- Repo conventions: workspace rules, `CLAUDE.md`, `.cursor/rules`

## Output

Report in chat only. Never post comments, approve, or request changes on GitHub, and never write to Jira, unless the user asks explicitly.

```markdown
## <KEY>: <summary>

<one-paragraph verdict: ready to merge / needs changes, and the main reason>

### Cross-PR issues
- ...

### <repo>#<n> <title> (CI: pass/fail)
- **Blocker**: <issue> — `path:line`, why it matters, suggested fix
- **Should fix**: ...
- **Nit**: ...

### Open questions
- ...
```

Link every PR as `[repo#n](url)` and cite code with `path:line`. Skip severity sections that have no findings.
