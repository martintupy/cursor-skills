# Cursor Plugins

The single source of shared Cursor skills and rules for all team repositories. It is a [Cursor team marketplace](https://cursor.com/docs/plugins.md#team-marketplaces): change a skill here once and every repository gets it, instead of copying it into each repo.

| Plugin | Contains | Install mode |
| --- | --- | --- |
| `dev-workflow` | Skills: `pull-request`, `jira-pr-review`, `vulnerability-scan` | Default On |
| `code-style` | Always-applied rule: `code-style` | Required |

## Use the plugins

### Team admin, once

Requires a Cursor Teams or Enterprise plan.

1. Install the [Cursor GitHub App](https://github.com/apps/cursor) on `Dius-ai/cursor-plugins`.
2. Open [Dashboard](https://cursor.com/dashboard) → **Plugins & MCPs** → **Team Marketplaces** → **Add Marketplace** → **Import from Repo**, and paste `https://github.com/Dius-ai/cursor-plugins`.
3. Under **Marketplace Settings**, turn on **Enable Auto Refresh** and save.
4. Set each plugin's install mode as shown in the table above.

### Developers

Nothing to do for Required and Default On plugins: they install automatically. Run **Developer: Reload Window** if you don't see them yet, then check **Customize** in the sidebar.

Remove any personal copies of these skills from `~/.cursor/skills/` and local copies from `~/.cursor/plugins/local/`, so you don't end up with two skills of the same name.

### Without a team plan

Install the plugins locally. Cursor ignores symlinks that point outside `~/.cursor/plugins/local`, so copy the files:

```bash
git clone git@github.com:Dius-ai/cursor-plugins.git
cd cursor-plugins
for plugin in dev-workflow code-style; do
  rsync -a --delete "$plugin/" "$HOME/.cursor/plugins/local/$plugin/"
done
```

Then run **Developer: Reload Window**. Rerun the loop after every `git pull`.

### Prerequisites for the skills

- `gh` authenticated with access to the Dius-ai org: `gh auth login`
- `acli` authenticated with dius-team.atlassian.net, for `jira-pr-review`: `acli jira auth login`
- Team repositories cloned next to each other (`~/github/<org>/datamap`, `~/github/<org>/dataapi`, ...), for cross-repo PR reviews

## Change a plugin

1. Edit the files on a branch and test them locally with the `rsync` loop above.
2. Open a PR. Once it merges to `main`, Auto Refresh publishes the change to the team within about 10 minutes.

To add a skill, create `<plugin>/skills/<skill-name>/SKILL.md` with `name` and `description` frontmatter; `name` must match the folder name. To add a rule, create `<plugin>/rules/<rule-name>.mdc` with `description` and `alwaysApply` (or `globs`) frontmatter. To add a plugin, create `<plugin>/.cursor-plugin/plugin.json` and list it in `.cursor-plugin/marketplace.json`. Paths must stay inside the plugin folder; `..` is not allowed.

## What belongs here

Add a skill or rule here when it applies to several repositories, such as PR workflow, Jira, code style or security scanning. Keep it in the repository's own `.cursor/skills/` or `AGENTS.md` when it only makes sense there, such as datamap's `aks-debug` or jarvis_core's `create-migration`.

Skills here must not hardcode one repository's commands or paths. Have them look these up in the repository's `AGENTS.md`, `Makefile` or a known file, the way `vulnerability-scan` reads `.cursor/security-context.md`.
