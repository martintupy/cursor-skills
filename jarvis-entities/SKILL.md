---
name: jarvis-entities
description: >-
  Plan and prepare changes to Jarvis agents, skills and tools defined in Datamap: resolve an
  entity's full context (prompts, referenced skills/tools, tool implementations in jarvis_core
  and datamap), split the request into code changes and manual Datamap edits, write paste-ready
  new prompts/descriptions to /tmp, and check dev/prod drift. Use when changing a Jarvis agent,
  skill, tool, system prompt or tool description, given a Datamap instance_id.
disable-model-invocation: true
---

# Jarvis entities

Input: a change request plus one or more Datamap `instance_id`s (agent, skill or tool) on **dev**.
If no instance_id was given, ask for it.

Repos: `jarvis_core` and `datamap`, cloned as siblings. Below, `<jarvis_core>` and `<datamap>`
mean the current repo or its sibling (`../jarvis_core`, `../datamap`). If one is missing, ask
the user for its path.

**Read-only towards Datamap.** Never call create/update/delete endpoints and never run
`promote_entities.py --apply`. Entity edits are applied manually by the user.

## Helper

Run from inside `<jarvis_core>` or `<datamap>` with the datamap venv:

```bash
PY=<datamap>/.venv/bin/python3
E=~/.cursor/skills/jarvis-entities/scripts/entities.py
$PY $E context <instance_id>... [-e dev|prod]          # closure tree + files
$PY $E diff <instance_id>... [-s dev] [-t prod]        # drift report + .diff files
```

Auth comes from datamap's `datamap-api` skill (`bruno/.env` with `DEV_API_TOKEN` and
`PROD_API_TOKEN`). The script finds datamap the same way; set `DATAMAP_REPO` if it is cloned
elsewhere. For anything else (e.g. finding an ID by name) use that skill directly.

- `context` writes `/tmp/jarvis-entities/<env>/<root>/`: `<kind>.<name>.json` (full instance)
  and `<kind>.<name>.<field>.txt` per text field (`system_prompt`, `prompt`, `description`).
- `diff` matches by instance_id, then by name for shared entities. It reports `IN SYNC`,
  `DRIFT` (changed fields, reference differences by name, and which side was edited last),
  `ONLY ON <ENV>` and `REACHABLE ONLY ON <ENV>`. It writes `--- dev / +++ prod` diffs to
  `/tmp/jarvis-entities/diff-<src>-<dst>/<root>/`. URLs that differ only by dev/prod host are
  reported as env-specific, not as drift.

## Workflow

```
- [ ] 1. Context on dev
- [ ] 2. Trace tool implementations
- [ ] 3. Drift baseline (dev vs prod)
- [ ] 4. Plan, confirmed with the user
- [ ] 5. Code changes (jarvis_core / datamap)
- [ ] 6. Entity edits written to /tmp
- [ ] 7. Prod parity plan
```

### 1. Context

Run `context` and read the tree. Read the agent `system_prompt`, every skill `prompt` and the
`description` of everything the request touches. Read the tool `.json` for `parameters_schema`
and `location_config`. Field definitions: `<datamap>/schemas/data/AI_agent.json`,
`AI_agent_skill.json` and `AI_tools.json`. Live data also carries fields outside these schemas
(`middleware`, `specialties`, `handoff_disabled`, `llm_model_config`, ...); keep them unless
they are part of the change.

How the runtime uses entities (verify in code, it changes):
- `<jarvis_core>/src/jarvis_core/core/loaders/entity_datamap_loader.py` loads them through
  `/instance/list/platform` (resource-policy filtered) and **silently skips** any entity that
  fails the models in `core/clients/datamap/schemas.py` (`AIAgentData`, `SkillData`,
  `AIToolData`). Check every proposed value against those models.
- An agent sees a skill's tools only through that skill. Prompts that name a tool must match
  `tool_name` exactly.

### 2. Trace tool implementations

| `location_config.type` | Where the code lives |
|---|---|
| `system` | `<jarvis_core>/src/<module_path as path>.py`, function `method` (defaults to tool name) |
| `rest_api` | URL host `datamap.*` or `*/api/datamap` → `<datamap>/src/routes.py`; other hosts are other services, so flag them |
| `mcp` | MCP server entity `server`, remote tool `tool_name` |

Check that `parameters_schema` matches the real function or endpoint signature, and that the
description and prompts describe what the code actually does.

### 3. Drift baseline

Run `diff` on the same IDs **before** planning. If prod is ahead on something you will touch
(`last edited on prod`, `ONLY ON PROD`, references only on prod), base the new content on the
prod version, or merge both, so the dev change does not drop prod functionality.

### 4. Plan

Classify every part of the request:

- **a. Code**: jarvis_core and/or datamap changes (new or changed tool functions, endpoints,
  schemas). Follow each repo's `CLAUDE.md`/`AGENTS.md`.
- **b. Entity edits**: `system_prompt`, `prompt`, `description`, `parameters_schema`,
  `location_config`, `allowed_tools` / `skills` references, new entities.

Present the plan and challenge the request where code and entities disagree, or where a prompt
change is compensating for a code problem. Wait for confirmation before step 5.

### 5. Code changes

Implement in the right repo with tests, following that repo's rules. Note any change that
entity edits depend on (a new `module_path`, a new endpoint), because it must ship first.

### 6. Entity edits to /tmp

Write to `/tmp/jarvis-entities/changes/<short-slug>/`:

- `<kind>.<name>.<field>.txt` for strings, `.json` for structured fields. **Exact paste-ready
  value only**: no headers or commentary. Write the full new value, not a fragment.
- `<kind>.<name>.<field>.diff`: `diff -u <context file> <new file>` against the current dev value.
- `CHANGES.md`: the index below.

For reference lists, write the complete new list with IDs for **each** env, because IDs can
differ between dev and prod (`diff` prints `matched by name: prod id ...`).

```markdown
# <title>

Request: <one line>

## Datamap edits (manual)

| # | Env | Entity | Instance ID | Field | New value | Diff |
|---|-----|--------|-------------|-------|-----------|------|
| 1 | dev | skill:<name> | <uuid> | prompt | skill.<name>.prompt.txt | skill.<name>.prompt.diff |

1. <why, one sentence per row>

## Code changes

- jarvis_core: <files / PR>
- datamap: <files / PR>

## Prod parity

### Backport to dev first (prod is ahead)
- <entity.field / reference>: <what, and its file>

### Promote to prod after dev is verified
1. Deploy code: <repo changes that prod entities depend on>
2. Entity edits on prod: <rows above with prod instance IDs, tools → skills → agents>

### Intentional differences
- <env-specific URLs, user-owned entities, ...>
```

### 7. Prod parity

Fill the "Prod parity" section from the `diff` output:

- **Backport**: anything prod has that dev lacks, so dev is a superset of prod.
- **Promote**: dev changes for prod, in dependency order (code deploy, then tools, skills, agents).
- If the user promotes with `<jarvis_core>/scripts/promote_entities.py`, give the export and the
  dry-run import commands only, and warn about these behaviours:
  - The snapshot is authoritative: references only on prod are **removed** unless you backport
    them first or pass `--keep-extra-refs`.
  - `location_config` is copied verbatim, so dev URLs (`*.dev.internal`) would land on prod.
  - Only shared (Jarvis system owned) entities are promoted. User-owned ones in the closure are
    skipped.

## Final report

In chat: what the agent/skill/tool does today (short), the plan split into code and entity
edits, the path to `CHANGES.md`, and drift findings, with prod-ahead items first.
