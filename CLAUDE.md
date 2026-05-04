# Wiki Repo Instructions

This is a **documentation wiki** — a separate repo that maintains agent doc files for a target repo and symlinks them in so LLM agents load them automatically.

## How it works

- `schema.yaml` — defines which paths in the target repo have managed docs
- `docs/` — all documentation files; mirrors the target repo's path structure
- Symlinks in the target repo point here; editing a file in `docs/` is immediately reflected
- `agent-wiki` CLI (or `scripts/wiki.py` shim) — all operations

## Key files

| File | Purpose |
|------|---------|
| `schema.yaml` | Source of truth for which paths have docs |
| `docs/<path>/<doc>` | Documentation for `<path>` in the target repo |
| `config.json` | Target repo path (set by `init`, gitignored) |
| `logs/drift.jsonl` | Source files changed since last sync |
| `logs/new-entry.jsonl` | Schema entries pending documentation |
| `logs/sync.jsonl` | Permanent sync history |

## When working in this repo

- All doc content goes in `docs/`. Never edit files outside `docs/` to document the target repo.
- To add a new documented path: add it to `schema.yaml`, then run `push`. The new entry is logged to `logs/new-entry.jsonl` with a placeholder doc. Populate it manually, then run `clear-flags --flag new_entry`.
- `config.json` is gitignored — each developer sets their own repo path via `init`.
- Docs placed at `docs/<path>/<doc>` cover only the code at or below `<path>`.
  Place shared concerns at the nearest common ancestor in the schema.

## Doc placement rules

- Each doc covers only the code **at or below** its path.
- Place content at the **highest level where it still applies exclusively**.
- A parent doc covers only: repo layout, tech stack, global conventions, interface overview, review/pattern rules.
- The LLM should propose deeper schema paths when it would meaningfully improve agent guidance — requires user confirmation before creation.

## Commands reference

```
agent-wiki init --repo-path <path>   # First-time setup (absorbs existing docs, installs hooks)
agent-wiki push                      # Sync symlinks with schema; logs new entries
agent-wiki push --verify             # Rebuild broken symlinks
agent-wiki pull                      # Absorb unmanaged doc files from the target
agent-wiki detect-drift              # Recompute drift from SourceCommitIDs (manual)
agent-wiki status [--scope X]        # Show pending drift statistics
agent-wiki clear-flags [--flag X]    # Clear flags; stamps SourceCommitID when clearing drift
```

## Updating documentation

When adding or changing any CLI command, flag, or workflow behavior, always update all four documentation surfaces together:

- **`README.md`** — user-facing project overview
- **`wiki/templates/wiki-instructions.md`** — written to `wiki-instructions.md` on `init`; the quickstart guide new users see
- **`wiki/templates/llm.md`** — written to `llm.md` on `init`; the reference loaded by LLMs working in target repos
- **`wiki/templates/WIKI_UPDATE.md`** — step-by-step drift/update guide symlinked into `.agent-wiki/`

These must stay in sync. A change documented in one but not the others will cause agents or users to act on stale information.
