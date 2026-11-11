"""Read-only Datamap helper for Jarvis agents, skills, tools and MCP servers.

``context`` resolves an entity's reference closure in one environment and dumps
every editable text field to its own file. ``diff`` compares the closure across
two environments (dev vs prod by default) and reports drift per entity.

Auth and environments come from the datamap repo's ``datamap-api`` skill
(``bruno/environments`` + ``bruno/.env``). The datamap clone is ``$DATAMAP_REPO``,
else the current repo or a sibling ``datamap`` of it. Run with the datamap venv:

    <datamap>/.venv/bin/python3 entities.py context <instance_id> -e dev
    <datamap>/.venv/bin/python3 entities.py diff <instance_id>
"""

import difflib
import importlib.util
import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from types import ModuleType
from typing import Annotated, Any

import httpx
import typer

CALL_PY_REL = Path(".cursor/skills/datamap-api/scripts/call.py")
OUT_ROOT = Path("/tmp/jarvis-entities")
JARVIS_SYSTEM_USER = "ffffffff-ffff-4fff-8fff-ffffffffffff"
BOOKKEEPING_KEYS = frozenset(
    {
        "uid",
        "instance_id",
        "created_at",
        "created_by",
        "updated_at",
        "merge_of",
        "completeness_score",
    }
)


@dataclass(frozen=True)
class Kind:
    """One Datamap entity type that makes up a Jarvis agent."""

    key: str
    schema_id: str
    name_key: str
    text_fields: tuple[str, ...]
    ref_fields: tuple[str, ...] = ()


KINDS: dict[str, Kind] = {
    k.schema_id: k
    for k in (
        Kind(
            "agent",
            "AI_agent.json",
            "agent_name",
            ("description", "system_prompt"),
            ("skills", "allowed_tools", "mcp_servers"),
        ),
        Kind(
            "skill",
            "AI_agent_skill.json",
            "skill_name",
            ("description", "prompt"),
            ("allowed_tools",),
        ),
        Kind("tool", "AI_tools.json", "tool_name", ("description",)),
        Kind("mcp", "MCP_server.json", "server_name", ("description",)),
    )
}


def _find_call_py() -> Path:
    """Locate datamap's ``datamap-api`` script: env var, current repo, or sibling."""
    if env_repo := os.environ.get("DATAMAP_REPO"):
        candidates = [Path(env_repo).expanduser()]
    else:
        cwd = Path.cwd()
        candidates = [p for d in (cwd, *cwd.parents) for p in (d, d / "datamap")]
    for repo in candidates:
        if (repo / CALL_PY_REL).is_file():
            return repo / CALL_PY_REL
    raise SystemExit(
        f"datamap-api skill ({CALL_PY_REL}) not found in DATAMAP_REPO, the current "
        "repo or a sibling 'datamap' clone; set DATAMAP_REPO"
    )


def _load_call_module() -> ModuleType:
    call_py = _find_call_py()
    spec = importlib.util.spec_from_file_location("datamap_call", call_py)
    if spec is None or spec.loader is None:
        raise SystemExit(f"cannot load {call_py}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


datamap_call = _load_call_module()
app = typer.Typer(add_completion=False, no_args_is_help=True)


@dataclass
class Entity:
    """A Datamap instance of one of the Jarvis kinds."""

    raw: dict[str, Any]

    @property
    def kind(self) -> Kind:
        return KINDS[self.raw["json_schema_id"]]

    @property
    def id(self) -> str:
        return str(self.raw["instance_id"])

    @property
    def data(self) -> dict[str, Any]:
        data = self.raw.get("data")
        return data if isinstance(data, dict) else {}

    @property
    def name(self) -> str:
        return str(self.data.get(self.kind.name_key) or f"<unnamed {self.id[:8]}>")

    @property
    def shared(self) -> bool:
        return str(self.raw.get("user_id")) == JARVIS_SYSTEM_USER

    @property
    def label(self) -> str:
        return f"{self.kind.key}:{self.name}"

    def refs(self, ref_field: str) -> list[str]:
        return [str(r) for r in (self.data.get(ref_field) or [])]


@dataclass
class Env:
    """Every Jarvis-kind instance visible to the token in one environment."""

    name: str
    by_id: dict[str, Entity] = field(default_factory=dict)

    def by_name(self, kind: Kind, name: str) -> Entity | None:
        """Shared instance of ``kind`` called ``name`` (personal ones never match)."""
        for entity in self.by_id.values():
            if entity.kind == kind and entity.shared and entity.name == name:
                return entity
        return None

    def closure(self, roots: list[str]) -> tuple[list[Entity], dict[str, list[str]]]:
        """Entities reachable from ``roots`` (BFS order) and dangling references."""
        order: list[Entity] = []
        dangling: dict[str, list[str]] = {}
        queue, seen = list(roots), set(roots)
        while queue:
            entity = self.by_id.get(queue.pop(0))
            if entity is None:
                continue
            order.append(entity)
            for ref_field in entity.kind.ref_fields:
                for ref_id in entity.refs(ref_field):
                    if ref_id not in self.by_id:
                        dangling.setdefault(f"{entity.label}.{ref_field}", []).append(
                            ref_id
                        )
                    elif ref_id not in seen:
                        seen.add(ref_id)
                        queue.append(ref_id)
        return order, dangling

    def ref_name(self, ref_id: str) -> str:
        entity = self.by_id.get(ref_id)
        return entity.label if entity else f"<missing {ref_id}>"


def _load_env(env_name: str) -> Env:
    base_url, client = datamap_call._connect(env_name)
    env = Env(env_name)
    with client:
        for schema_id in KINDS:
            body = {"json_schema_id": schema_id, "owner_scope": {"type": "all"}}
            resp: httpx.Response = datamap_call._request(
                client, "POST", f"{base_url}/instance/list", json.dumps(body).encode()
            )
            if resp.status_code != 200:
                raise SystemExit(
                    f"{env_name} /instance/list {schema_id}: HTTP {resp.status_code} "
                    f"{resp.text[:300]}"
                )
            for raw in resp.json().get("instances", []):
                env.by_id[str(raw["instance_id"])] = Entity(raw)
    return env


def _slug(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", name).strip("_") or "unnamed"


def _stems(entities: list[Entity]) -> dict[str, str]:
    """File stem per entity id, suffixed with the short id on name collisions."""
    stems: dict[str, str] = {}
    used: set[str] = set()
    for entity in entities:
        stem = f"{entity.kind.key}.{_slug(entity.name)}"
        if stem in used:
            stem = f"{stem}-{entity.id[:8]}"
        used.add(stem)
        stems[entity.id] = stem
    return stems


def _location(entity: Entity) -> str:
    loc = entity.data.get("location_config")
    if not isinstance(loc, dict):
        return ""
    match loc.get("type"):
        case "system":
            method = loc.get("method") or entity.name
            return f"system {loc.get('module_path')}:{method}"
        case "rest_api":
            return f"rest_api {loc.get('method')} {loc.get('url')}"
        case "mcp":
            return f"mcp {loc.get('server')}/{loc.get('tool_name')}"
        case other:
            return f"{other}"


def _describe(entity: Entity) -> str:
    owner = "shared" if entity.shared else f"owner={entity.raw.get('user_id')}"
    parts = [entity.label, entity.id, owner]
    if status := entity.data.get("status"):
        parts.append(f"status={status}")
    if location := _location(entity):
        parts.append(location)
    return "  ".join(parts)


def _print_tree(
    env: Env, root: str, depth: int = 0, seen: set[str] | None = None
) -> None:
    seen = seen if seen is not None else set()
    entity = env.by_id.get(root)
    if entity is None:
        typer.echo(f"{'  ' * depth}<missing {root}>")
        return
    suffix = "  (see above)" if entity.id in seen else ""
    typer.echo(f"{'  ' * depth}{_describe(entity)}{suffix}")
    if suffix:
        return
    seen.add(entity.id)
    for ref_field in entity.kind.ref_fields:
        for ref_id in entity.refs(ref_field):
            _print_tree(env, ref_id, depth + 1, seen)


def _write_entity_files(out: Path, stem: str, entity: Entity) -> None:
    (out / f"{stem}.json").write_text(
        json.dumps(entity.raw, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    for text_field in entity.kind.text_fields:
        value = entity.data.get(text_field)
        if isinstance(value, str):
            (out / f"{stem}.{text_field}.txt").write_text(value, encoding="utf-8")


@app.command()
def context(
    instance_ids: Annotated[list[str], typer.Argument(help="Agent/skill/tool IDs")],
    env: Annotated[str, typer.Option("--env", "-e")] = "dev",
    out: Annotated[Path | None, typer.Option(help="Output dir")] = None,
) -> None:
    """Resolve the reference closure and dump each entity to files."""
    loaded = _load_env(env)
    unknown = [i for i in instance_ids if i not in loaded.by_id]
    if unknown:
        raise SystemExit(f"not an agent/skill/tool/mcp instance on {env}: {unknown}")
    entities, dangling = loaded.closure(instance_ids)
    target = out or OUT_ROOT / env / _slug(loaded.by_id[instance_ids[0]].name)
    target.mkdir(parents=True, exist_ok=True)
    stems = _stems(entities)
    for entity in entities:
        _write_entity_files(target, stems[entity.id], entity)

    typer.echo(f"# {env} closure ({len(entities)} entities)\n")
    for root in instance_ids:
        _print_tree(loaded, root)
    personal = [e for e in entities if not e.shared]
    if personal:
        typer.echo("\nNot shared (user-owned; not promotable by promote_entities.py):")
        for entity in personal:
            typer.echo(f"  {entity.label}  owner={entity.raw.get('user_id')}")
    if dangling:
        typer.echo("\nWARNING references resolving to nothing:")
        for label, ids in dangling.items():
            typer.echo(f"  {label}: {ids}")
    typer.echo(f"\nfiles: {target}")


def _env_neutral(value: Any) -> Any:
    """``value`` with dev/prod host segments in URLs replaced by a placeholder."""
    dumped = json.dumps(value, ensure_ascii=False, sort_keys=True)
    return re.sub(r"(://[^/\s\"]*?)\b(dev|prod)\b", r"\1<env>", dumped)


def _compare_value(src: Any, dst: Any) -> list[str]:
    if isinstance(src, str) and isinstance(dst, str):
        return list(
            difflib.unified_diff(src.splitlines(), dst.splitlines(), lineterm="")
        )
    src_lines = json.dumps(
        src, ensure_ascii=False, indent=2, sort_keys=True
    ).splitlines()
    dst_lines = json.dumps(
        dst, ensure_ascii=False, indent=2, sort_keys=True
    ).splitlines()
    return list(difflib.unified_diff(src_lines, dst_lines, lineterm=""))


def _ref_drift(a: Entity, b: Entity, src: Env, dst: Env) -> list[str]:
    lines: list[str] = []
    for ref_field in a.kind.ref_fields:
        src_names = {src.ref_name(r) for r in a.refs(ref_field)}
        dst_names = {dst.ref_name(r) for r in b.refs(ref_field)}
        if only_dst := sorted(dst_names - src_names):
            lines.append(f"{ref_field} only on {dst.name}: {only_dst}")
        if only_src := sorted(src_names - dst_names):
            lines.append(f"{ref_field} only on {src.name}: {only_src}")
    return lines


@app.command()
def diff(
    instance_ids: Annotated[list[str], typer.Argument(help="IDs on the source env")],
    source: Annotated[str, typer.Option("--source", "-s")] = "dev",
    target: Annotated[str, typer.Option("--target", "-t")] = "prod",
    out: Annotated[Path | None, typer.Option(help="Output dir for .diff files")] = None,
) -> None:
    """Compare the closure on SOURCE against TARGET (matched by ID, then name)."""
    src, dst = _load_env(source), _load_env(target)
    unknown = [i for i in instance_ids if i not in src.by_id]
    if unknown:
        raise SystemExit(f"not an agent/skill/tool/mcp instance on {source}: {unknown}")

    def match(entity: Entity, other: Env) -> Entity | None:
        return other.by_id.get(entity.id) or (
            other.by_name(entity.kind, entity.name) if entity.shared else None
        )

    src_entities, src_dangling = src.closure(instance_ids)
    dst_roots = [m.id for i in instance_ids if (m := match(src.by_id[i], dst))]
    dst_entities, dst_dangling = dst.closure(dst_roots)

    root_name = _slug(src.by_id[instance_ids[0]].name)
    out_dir = out or OUT_ROOT / f"diff-{source}-{target}" / root_name
    out_dir.mkdir(parents=True, exist_ok=True)
    stems = _stems(src_entities)

    typer.echo(
        f"# {source} -> {target}  ({len(src_entities)} vs {len(dst_entities)})\n"
    )
    matched_dst: set[str] = set()
    for a in src_entities:
        b = match(a, dst)
        if b is None:
            typer.echo(f"ONLY ON {source.upper()}  {_describe(a)}")
            continue
        matched_dst.add(b.id)
        header = f"{a.label}"
        if a.id != b.id:
            header += f"  (matched by name: {target} id {b.id})"
        changed: list[str] = []
        env_specific: list[str] = []
        for key in sorted(
            {*a.data, *b.data} - BOOKKEEPING_KEYS - set(a.kind.ref_fields)
        ):
            if a.data.get(key) == b.data.get(key):
                continue
            if _env_neutral(a.data.get(key)) == _env_neutral(b.data.get(key)):
                env_specific.append(key)
                continue
            changed.append(key)
            lines = _compare_value(a.data.get(key), b.data.get(key))
            path = out_dir / f"{stems[a.id]}.{key}.diff"
            path.write_text(
                f"--- {source}\n+++ {target}\n" + "\n".join(lines[2:]) + "\n",
                encoding="utf-8",
            )
        refs = _ref_drift(a, b, src, dst)
        if env_specific:
            header += f"  [env-specific URLs only in: {env_specific}]"
        if not changed and not refs:
            typer.echo(f"IN SYNC  {header}")
            continue
        newer = (
            target
            if str(b.raw.get("updated_at")) > str(a.raw.get("updated_at"))
            else source
        )
        typer.echo(f"DRIFT  {header}  (last edited on {newer})")
        if changed:
            typer.echo(f"  fields: {changed}")
        for line in refs:
            typer.echo(f"  {line}")

    for b in dst_entities:
        if b.id not in matched_dst and match(b, src) is None:
            typer.echo(f"ONLY ON {target.upper()}  {_describe(b)}")
        elif b.id not in matched_dst:
            typer.echo(
                f"REACHABLE ONLY ON {target.upper()}  {b.label} "
                f"(exists on {source} but not referenced there)"
            )

    for env_name, dangling in ((source, src_dangling), (target, dst_dangling)):
        for label, ids in dangling.items():
            typer.echo(f"WARNING {env_name} {label} resolves to nothing: {ids}")
    typer.echo(f"\ndiff files: {out_dir}")


if __name__ == "__main__":
    app()
