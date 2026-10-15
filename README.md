# Cursor Skills

Shared Cursor skills for all team repositories. Cursor loads every skill in `~/.cursor/skills/`, so cloning this repo there makes the skills available in every project, and `git pull` keeps them up to date.

| Skill | Use it for | Trigger |
| --- | --- | --- |
| `pull-request` | Create or update a PR with a Conventional Commits title and structured description | `/pull-request` |
| `jira-pr-review` | Review all PRs linked to a Jira ticket across repositories | Automatic when you mention a Jira key or URL |
| `vulnerability-scan` | Security audit of the current repository | `/vulnerability-scan` |

## Install

1. Install and log in to the CLIs the skills use:

   ```bash
   brew install gh && gh auth login
   brew tap atlassian/acli && brew install acli && acli jira auth login
   ```

2. Turn your personal skills folder into a checkout of this repo. This works whether `~/.cursor/skills` is missing, empty or already holds your own skills, which stay untracked:

   ```bash
   mkdir -p ~/.cursor/skills && cd ~/.cursor/skills
   git init -b main
   git remote add origin https://github.com/martintupy/cursor-skills.git
   git pull origin main
   git branch -u origin/main
   ```

   If `git pull` stops with "untracked working tree files would be overwritten", one of your own skills has the same name as a shared one. Rename or remove yours and run `git pull origin main` again.

3. Restart Cursor, or run **Developer: Reload Window**, and check that the skills appear under **Customize** → **Skills**.

## Update

```bash
git -C ~/.cursor/skills pull
```

## Change or add a skill

Edit directly in `~/.cursor/skills`, on a branch, and open a PR:

1. Create `<skill-name>/SKILL.md` at the top level, with `name` (equal to the folder name) and `description` frontmatter. Cursor does not find skills nested deeper.
2. Add `disable-model-invocation: true` to the frontmatter if the skill should only run when called with `/<skill-name>`.
3. Reload Cursor and try the skill before opening the PR.

## What belongs here

A skill belongs here when it applies to several repositories. It stays in the repository's own `.cursor/skills/` when it only makes sense there, such as datamap's `aks-debug` or jarvis_core's `create-migration`.

Skills here must not hardcode one repository's commands or paths. They should look them up in the repository's `AGENTS.md`, `Makefile` or a known file, the way `vulnerability-scan` reads `.cursor/security-context.md`.

Rules, such as code style, are not shared through this repo: Cursor has no file-based user-level rules. Keep them in each repository's `AGENTS.md` or `.cursor/rules/`.
