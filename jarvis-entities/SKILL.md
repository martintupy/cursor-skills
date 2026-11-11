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
$PY $E context <instance_id>... -r <slug> [-e dev|prod]    # closure tree + files
$PY $E diff <instance_id>... -r <slug> [-s dev] [-t prod]  # drift report + .diff files
```

Auth comes from datamap's `datamap-api` skill (`bruno/.env` with `DEV_API_TOKEN` and
`PROD_API_TOKEN`). The script finds datamap the same way; set `DATAMAP_REPO` if it is cloned
elsewhere. For anything else (e.g. finding an ID by name) use that skill directly.

Pick one short kebab-case `<slug>` per request and pass it to every call. Everything for the
request lives in `/tmp/jarvis-entities/<slug>/`; the script writes only to its `.scratch/`:

- `context` → `.scratch/<env>/`: `<kind>.<name>.json` (full instance) and
  `<kind>.<name>.<field>.txt` per text field (`system_prompt`, `prompt`, `description`).
- `diff` → `.scratch/diff-<src>-<dst>/`: `--- dev / +++ prod` diffs per drifting field. It
  matches by instance_id, then by name for shared entities, and reports `IN SYNC`, `DRIFT`
  (changed fields, reference differences by name, which side was edited last), `ONLY ON <ENV>`
  and `REACHABLE ONLY ON <ENV>`. URLs differing only by dev/prod host, and scalar lists differing
  only in order (e.g. `required`), are noted on the entity line, not reported as drift.

## Workflow

```
- [ ] 1. Context on dev
- [ ] 2. Trace tool implementations
- [ ] 3. Drift baseline (dev vs prod)
- [ ] 4. Plan, confirmed with the user
- [ ] 5. Code changes (jarvis_core / datamap)
- [ ] 6. Entity edits + README.md in /tmp/jarvis-entities/<slug>/
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

Tool descriptions are shared by every skill and agent that attaches the tool: keep them
generic and concise (what it does, inputs, what it returns). Workflow-specific guidance (which
tool to call when, how to use a returned field) belongs in the skill or agent prompt.

Present the plan and challenge the request where code and entities disagree, or where a prompt
change is compensating for a code problem. Wait for confirmation before step 5.

### 5. Code changes

Implement in the right repo with tests, following that repo's rules. Note any change that
entity edits depend on (a new `module_path`, a new endpoint), because it must ship first.

### 6. Entity edits to /tmp

Layout of `/tmp/jarvis-entities/<slug>/`:

```
README.md                         # the only file the user has to read
dev/1-<kind>-<name>-<field>.txt   # paste-ready values, numbered = README step
prod/4-<kind>-<name>-<field>.txt  # numbering continues after dev
review/<env>-<n>-....diff         # current value vs new value, per step
.scratch/                         # script output; never referenced from README steps
```

- One file per field edit, `.txt` for strings and `.json` for structured fields. **Exact
  paste-ready value only**: no headers or commentary, the full new value, not a fragment.
- Order steps by dependency: tools, then skills, then agents (a prompt must not name a tool
  before it is attached).
- Reference lists: write the complete new list with that env's IDs (IDs can differ, see
  `matched by name: prod id ...` in the diff). Name the added/removed entities in the step.
- Review diffs: `diff -u --label current --label new <.scratch file> <new file>`.

`README.md` template (keep it this short; detail goes in "Why"):

```markdown
# <title>

<one sentence: what changes and why>

## On dev now

1. **tool `<name>`** (`<instance_id>`) → field `description`
   paste `dev/1-tool-<name>-description.txt`
2. **skill `<name>`** (`<instance_id>`) → field `allowed_tools`
   paste `dev/2-skill-<name>-allowed_tools.json` (adds `<tool>`, `<tool>`)
3. ...

## On prod later (after dev is verified)

0. Deploy code first: <repo changes prod depends on, or "nothing">
4. ...

## Why

- Step 1: <one sentence>
- Prod was ahead on <...>; folded into step <n>.

## Not changed / open issues

- <intentional env differences, open questions>
```

Steps with no prod counterpart, or prod-only backports, still get a number in the right
section. If the user supplied a studio URL, add it to that entity's step.

### 7. Prod parity

Fill the "On prod later", "Why" and "Not changed" sections from the `diff` output:

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

In chat: what the agent/skill/tool does today (short), the path to `README.md`, the dev steps
as a short numbered list, and drift findings, with prod-ahead items first.
