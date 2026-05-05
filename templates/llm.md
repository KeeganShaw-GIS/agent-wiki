# agent-wiki — LLM Reference

This file lives at `.agent-wiki/llm.md` and is linked from `AGENT-INDEX.md`.

`.agent-wiki/` IS the wiki — a nested git repo inside the target repo with its own history
and remote. Docs live at `.agent-wiki/docs/`, committed to the wiki history and gitignored
from the main repo. Every managed path has a symlink next to the code that points into
`.agent-wiki/docs/`.

## Directory layout

```
<target-repo>/
├── .gitignore                   # includes .agent-wiki/
├── src/
│   └── CLAUDE.md                # symlink → ../.agent-wiki/docs/src/CLAUDE.md
├── CLAUDE.md                    # symlink → .agent-wiki/docs/CLAUDE.md
└── .agent-wiki/                 # nested git repo (own history, own remote)
    ├── .git/
    ├── schema.yaml              # committed — which paths are managed
    ├── config.json              # committed — doc_filename
    ├── docs/                    # committed — all documentation
    ├── templates/               # committed — customisable templates
    ├── llm.md                   # committed — this file
    ├── AGENT-INDEX.md           # regenerated — navigation hub
    ├── wiki                     # wrapper: exec agent-wiki "$@"
    ├── logs/                    # gitignored — flags.json, drift.jsonl, etc.
    ├── symlinks/                # gitignored — flat mirror, regenerated
    └── agents/                  # gitignored — symlinks into templates/
        ├── WIKI_UPDATE.md       → ../templates/WIKI_UPDATE.md
        └── WIKI_MERGE.md        → ../templates/WIKI_MERGE.md
```

## ⚠ Symlink mechanic — read before editing

Files in `.agent-wiki/agents/` are symlinks back into `.agent-wiki/`. Editing
`.agent-wiki/agents/llm.md` edits `.agent-wiki/llm.md` — the committed source.

Doc symlinks in the target repo (e.g. `src/CLAUDE.md`) point to `.agent-wiki/docs/src/CLAUDE.md`.
Editing the symlink edits the wiki doc directly. Do not copy these files or duplicate content.

## Checking flags before any doc work

Always read `.agent-wiki/logs/flags.json` before starting any task that touches documentation.
A missing key means no action needed for that concern.

| Flag | Meaning | How to resolve |
|------|---------|----------------|
| `new_entry` | New schema paths were added; placeholder docs exist | Read `new-entry.jsonl` for the paths. Populate each doc. Run `clear-flags --flag new_entry` when done. |
| `drift_detected` | Source files changed since docs were last reviewed | Read `drift.jsonl` — each entry has `from_commit`, `to_commit`, `changed_files`. Run `git diff <from>.. <to> -- <path>/`. Update affected docs per `WIKI_UPDATE.md`. Run `clear-flags --flag drift_detected` when done (stamps `SourceCommitID=HEAD`). |
| `multiple_versions` | Both a wiki doc and an unmanaged repo file exist at the same path | Read `conflict.jsonl`. Resolve via `pull --strategy wiki` or `pull --strategy repo`, then `clear-flags`. |

Example:
```json
{
  "new_entry": true,
  "drift_detected": true,
  "last_updated": "2026-05-05T10:00:00Z"
}
```

## schema.yaml

Controls which paths have managed doc files. Located at `.agent-wiki/schema.yaml`.

| Suffix | Meaning |
|--------|---------|
| `+`    | Managed — doc in `docs/` + symlink in target |
| `~`    | Untracked — real file stays in target, wiki ignores it |
| (none) | Structural container only, no doc |

`root+` is the sentinel for the repo root (maps to `docs/<doc_filename>`).

## Adding a new documented path

1. Edit `.agent-wiki/schema.yaml` — add the path with `+`
2. Run `agent-wiki push` (or `.agent-wiki/wiki push`) — creates placeholder doc + symlink, logs to `new-entry.jsonl`, sets `new_entry` flag
3. Populate the placeholder doc
4. Run `agent-wiki clear-flags --flag new_entry` when done

## Running commands

From anywhere in the target repo:

```bash
agent-wiki push
agent-wiki status
agent-wiki detect-drift
```

Or via the wrapper (useful when `agent-wiki` may not be on PATH):

```bash
.agent-wiki/wiki push
.agent-wiki/wiki status
```

## Commands

| Command | What it does |
|---------|-------------|
| `init [--doc-filename X] [--wiki-remote <url>]` | One-time setup: `git init .agent-wiki/`, absorb existing docs, create symlinks, install hooks |
| `push` | Reconcile schema ↔ docs ↔ symlinks; log new entries; regenerate AGENT-INDEX.md |
| `push --verify` | Rebuild any broken or missing symlinks |
| `pull [--strategy repo\|wiki\|skip]` | Scan target for unmanaged doc files and absorb them |
| `detect-drift [--staged]` | Recompute drift from SourceCommitIDs; log per-doc entries |
| `status [--scope X]` | Show pending drift statistics |
| `eject [--scope X] [--purge]` | Copy docs back as real files, detach from wiki; `--purge` removes `.agent-wiki/` entirely |
| `clear-flags [--flag X]` | Clear one or all flags; auto-clears flags whose log is empty |
| `hook-setup` | (Re)install git hooks and wrapper script |

## hook-setup stages

| Stage | Flag to skip | What it does |
|-------|-------------|--------------|
| `pre-commit` | `--no-pre-commit` | Runs `detect-drift --staged` before each commit. Non-blocking (always exits 0). |
| `post-checkout` | `--no-post-checkout` | Runs `push` after checkout or clone to create missing docs and symlinks. |

## Doc metadata header

Every managed doc has this block at the top:

```
<!-- agent-wiki
Check .agent-wiki/flags.json before starting doc work.
LLM Guide: .agent-wiki/agents/llm.md
Wiki Index: .agent-wiki/AGENT-INDEX.md

Location: src/CLAUDE.md
LastTouchedBy: agent-wiki push
ChangeDate: 2026-05-05
WikiCommitID: abc1234
SourceCommitID: def5678
-->
```

`SourceCommitID` is the target repo commit the doc was last reviewed against.
Do not edit or remove this block. It is stripped automatically on `eject`.

## Recovery

```bash
git clone <wiki-remote> .agent-wiki/
agent-wiki push --verify    # restores all symlinks
```

## Key invariants

- `agent-wiki` can be run from anywhere inside the target repo — it walks up to find `.agent-wiki/schema.yaml`.
- `.agent-wiki/docs/<path>/<doc>` is the source of truth for doc content. Symlinks in the target repo are pointers.
- `schema.yaml` is the source of truth for which paths are managed.
- `logs/` is gitignored — it is operational state, not committed history.
- `instructions.md`, `WIKI_UPDATE.md`, and `WIKI_MERGE.md` are user-owned — never overwritten after first creation.
