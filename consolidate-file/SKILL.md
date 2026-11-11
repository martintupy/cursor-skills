---
name: consolidate-file
description: Make a file read as one coherent unit after feature work by removing duplicated logic and redundant methods, reusing existing shared code, aligning it with the file's own conventions, and ordering its constants, helpers, classes and methods into a predictable layout. Use when asked to consolidate, deduplicate, clean up, organize or integrate a specific file.
disable-model-invocation: true
---

# Consolidate File

Feature work tends to tunnel: new code solves the task but ignores helpers, patterns and abstractions that already exist in the file or the codebase. Review the target as the maintainer of the whole file, not as the author of the latest feature. If this runs in the same chat that wrote the code, treat the earlier design decisions as unverified.

## 1. Pick the target

- The target is the file or files the user references. If none is referenced, use the file currently focused in the editor, and confirm with `AskQuestion` if that is ambiguous
- The whole file is in scope, not only recent edits
- Run `git diff HEAD -- <file>` to see what was added recently. Those parts are the most likely source of overlap, so check them first

## 2. Map the file and its surroundings

Read the entire file and list its functions, methods, classes, constants and types with a one-line note on what each does.

Then read what it depends on and what sits next to it: the repository modules it imports, sibling files in the same directory (other services, repositories, routers, components), and shared modules (`utils`, `common`, `core`, `lib`, `helpers`, base classes, mixins, hooks).

Note the file's dominant conventions: error handling, logging, naming, validation, config access, data access.

## 3. Hunt for overlap

**Inside the file**, compare the symbols against each other:

- Two methods doing the same thing under different names, or differing only by a value that could be a parameter
- Repeated blocks that should be one helper
- Pass-through wrappers and trivial getters
- Single-use helpers: keep one only if it names a rule the caller would otherwise have to explain, such as an interval overlap or a null-safe comparison, or if it keeps the caller under the size limit. Inline it when the body is a short expression the call site reads just as well without, e.g. a one-line tuple comparison
- Methods that never use `self`: make them private module-level functions, not `@staticmethod`s or private methods
- Code that handles errors, logging or naming differently from the rest of the file
- Unused functions, parameters, imports and leftovers from earlier iterations

**Against the codebase**, for each symbol defined in the file:

- Grep for name tokens and synonyms (`get_user`, `fetch_user`, `load_user`), for the key calls in its body (same table, endpoint, query, library call), and for distinctive literals
- Check whether the standard library or an existing dependency already provides it
- Check whether generic logic in this file belongs in an existing shared module

Classify each finding:

| Finding | Action |
| --- | --- |
| Duplicate: the behavior already exists elsewhere | Call the existing code, delete the local copy |
| Near-duplicate: other code covers most of it | Merge only if the result stays simple; otherwise keep both and say why |
| Redundant layer | Inline it |
| Repetition | Merge into one place |
| Convention drift | Align with the file's dominant style |
| Misplaced generic logic | Move it to an existing shared module; never create a new `utils` module for one caller |
| Dead code | Delete |

## 4. Organize the layout

After the overlap fixes, order the file so a reader finds things where they expect them. If the project or language already defines a layout (linter member-ordering rules, a style guide, a sibling file everyone copies), follow it instead.

Top to bottom, so the file opens on its public API:

1. Imports, as the formatter sorts them
2. Small types the public API exposes or depends on (`NamedTuple`, dataclasses, enums, interfaces)
3. The main public class or exported functions
4. Private helpers, grouped by concern, e.g. query rendering, parameter building, result decoding
5. An entry-point guard such as `if __name__ == "__main__"`, if any, last

Why this order:

- Python resolves a name when the code runs, not where it is defined, so methods can call helpers defined below the class. Putting helpers first is a habit, not a requirement, and it pushes the public API hundreds of lines down
- The only real ordering constraint is code that runs at import time: module-level constants built by calling a helper, default arguments, decorators and base classes. The helpers they call must sit above them

Within each group:

- Group by concern first. A constant goes with the helpers of its concern, whether it is literal or derived. For example, all Cypher subquery fragments sit together, not split between the top of the file and the helper section
- Inside a helper group, put the higher-level helpers first and the primitives they call below them, the same top-down direction as the file as a whole
- When an import-time constant forces a helper above it, keep that helper and the constant together inside their concern group rather than moving the whole group to the top
- Keep pairs together: a helper next to its inverse or sibling (`_encode`/`_decode`, `_same_value`/`_same_bound`), a constant next to the only function that uses it
- Inside a class, list `__init__` and the dunder methods first, then the private primitives the other methods build on, such as `_execute`. Then group the public methods by the resource they act on, with each group in create, read, update, delete order. A method goes in the group of the resource it reads or writes, not the group its name suggests. Put bulk and admin operations (clone, merge, purge) last
- Order by concern, never by when the code was added. Code from the latest feature should not end up as a block at the bottom
- If one concern's helpers make up a large part of the file, propose moving them to a sibling module and ask with `AskQuestion` before creating it. Do not add section-divider comments

Moves only:

- Reorder without changing code in the same step, so the diff can be reviewed with `git diff --color-moved`
- Suggest that the user commits the reorder separately from the consolidation edits
- If reordering would move most of the file, show the proposed outline and ask with `AskQuestion` before moving anything

## 5. Guardrails

- Do not extract an abstraction for two small similar snippets. Duplication is cheaper than the wrong abstraction
- Code that looks similar but differs for a domain reason stays separate
- Outside the target file, change code only to reuse or extend it, never to tidy it
- Before changing the signature or behavior of anything used outside the target file, find all its callers. If any would be affected, ask with `AskQuestion` before editing
- Keep the file's public interface and external behavior unchanged unless the user agrees otherwise
- If the cleanup would rewrite most of the file, present the findings and ask before editing

## 6. Apply and verify

1. Make the edits
2. Grep every removed or renamed symbol to confirm nothing still references it
3. Find the test and lint commands in `AGENTS.md`, `CLAUDE.md`, the `Makefile` or `.pre-commit-config.yaml`, and run them for the affected areas. If none exist, say so

## 7. Report

- Each consolidation: what was removed, reused, merged or moved, citing the code it now relies on
- The final outline of the file: one line per group with the symbols in order
- Overlaps deliberately left in place, with the reason
- Net effect from `git diff --stat`
- Nothing found is a valid result; state it instead of inventing changes
