# agent-wiki — LLM Reference

This directory is an **agent-wiki** wiki root. It holds agent doc files for a target
git repo and symlinks them in so your LLM agent loads them automatically at the correct path depth.

The doc filename (e.g. `CLAUDE.md`, `AGENTS.md`) is set in `config.json` under `doc_filename`.

## Directory layout

```
<wiki-root>/
├── schema.yaml          # Which paths in the target repo are documented
├── config.json          # Target repo path + doc_filename — gitignored, set by `init`
├── docs/                # All documentation; mirrors target repo structure
│   └── <path>/<doc>
├── templates/
│   ├── AGENT.template.md   # Placeholder written when push creates a new doc
│   ├── instructions.md      # House rules for writing doc content
│   ├── WIKI_UPDATE.md       # Step-by-step guide for updating docs manually
│   └── WIKI_MERGE.md        # Step-by-step guide for resolving doc conflicts
├── logs/
│   ├── drift.jsonl      # Source files changed since last doc sync
│   ├── new-entry.jsonl  # New schema paths pending documentation
│   ├── conflict.jsonl   # Paths with both a wiki doc and an unmanaged repo file
│   ├── flags.json       # Current wiki status flags (see below)
│   └── sync.jsonl       # Permanent sync history
└── llm.md               # This file

<target-repo>/
├── <doc>                # Symlink → .agent-wiki/AGENT-INDEX.md  (root entry point)
├── <path>/<doc>         # Symlinks for each managed path → wiki docs
└── .agent-wiki/        # Gitignored — created by `hook-setup`
    ├── AGENT-INDEX.md   # Generated navigation hub (full doc tree + agent links)
    ├── <doc>            # Mirror symlink → wiki docs/<doc>
    ├── <path>/<doc>     # Mirror symlinks for each managed path
    ├── wiki             # Wrapper script: runs agent-wiki from within the target repo
    ├── wiki-path        # Path to this wiki root (read by wrapper)
    ├── flags.json       # Symlink → <wiki>/logs/flags.json
    ├── schema.yaml      # Symlink → <wiki>/schema.yaml
    ├── AGENT.template.md  # Symlink → <wiki>/templates/AGENT.template.md
    ├── instructions.md     # Symlink → <wiki>/templates/instructions.md
    └── agents/             # LLM guidance docs (symlinks + user-added blank docs)
        ├── llm.md          # Symlink → <wiki>/llm.md  (this file)
        ├── WIKI_UPDATE.md  # Symlink → <wiki>/templates/WIKI_UPDATE.md
        ├── WIKI_MERGE.md   # Symlink → <wiki>/templates/WIKI_MERGE.md
        └── <name>.md       # User-added agent docs (via `add-agent --name <name>`)
```

## ⚠ Symlink mechanic — read before editing

**Files in `.agent-wiki/` and `.agent-wiki/agents/` are symlinks back to the wiki.** Editing `.agent-wiki/schema.yaml`
edits the canonical `schema.yaml` in the wiki root. The same applies to `AGENT.template.md` and the files in `agents/`.

**Do not copy these files.** Do not duplicate content from them into doc files.
Instead, reference them by path and use the CLI to act on them:

- To add a new documented path → edit `.agent-wiki/schema.yaml`, then run `.agent-wiki/wiki push`
- To absorb an unmanaged doc → run `.agent-wiki/wiki pull`
- To repair broken symlinks → run `.agent-wiki/wiki push --verify`
- To check what needs attention → run `.agent-wiki/wiki status`

## Checking flags before any doc work

Always read `.agent-wiki/flags.json` before starting any task that touches documentation.
Flags signal pending work. A missing key means no action needed for that concern.

| Flag | Meaning | How to resolve |
|------|---------|----------------|
| `new_entry` | New schema paths were added; placeholder docs exist | Read `new-entry.jsonl` for the paths. Populate each doc manually. Run `clear-flags --flag new_entry` when done. |
| `drift_detected` | Source files changed since docs were last reviewed | Read `drift.jsonl` — each entry has `from_commit`, `to_commit`, and `changed_files`. Run `git diff <from_commit>..<to_commit> -- <path>/` to see what changed. Update affected docs following `.agent-wiki/agents/WIKI_UPDATE.md`. Run `clear-flags --flag drift_detected` when done — this stamps `SourceCommitID=HEAD` on each drifted doc. |
| `multiple_versions` | Both a wiki doc and an unmanaged repo file exist at the same path | Read `conflict.jsonl` for the paths. Resolve each by running `pull --strategy wiki` or `pull --strategy repo`. Run `clear-flags` when done — it auto-clears if the conflict log is empty. |
| `docs_out_of_sync` | Broken/missing symlinks were found and repaired | Run `.agent-wiki/wiki push --verify` to ensure all symlinks are intact. Check if any repaired docs have placeholder content and populate them manually. |

Example flags.json:
```json
{
  "new_entry": true,
  "drift_detected": true,
  "multiple_versions": true,
  "last_updated": "2026-05-03T10:00:00Z"
}
```

## schema.yaml

Controls which paths have managed doc files. Edit via `.agent-wiki/schema.yaml`.

| Suffix | Meaning |
|--------|---------|
| `+`    | Managed — has a doc in `docs/` and a symlink in the target |
| `~`    | Untracked — real file stays in target, wiki ignores it |
| (none) | Structural — nesting container only, no doc |

`root+` is the sentinel for the repo root (maps to `docs/<doc>`).

## Adding a new documented path

1. Edit `.agent-wiki/schema.yaml` — add the path with `+` (e.g. `frontend/payments+:`)
2. Run `.agent-wiki/wiki push` — creates placeholder doc + symlink, logs to `new-entry.jsonl`,
   sets `new_entry` flag
3. Populate the new doc manually
4. Run `.agent-wiki/wiki clear-flags --flag new_entry` when done

## Commands

| Command | What it does |
|---------|-------------|
| `init --repo-path <path>` | One-time setup: save config, absorb existing docs, create symlinks, install hooks |
| `hook-setup` | (Re)create `.agent-wiki/` and install git hooks in the target repo |
| `push` | Reconcile schema ↔ docs ↔ symlinks; log new entries; regenerate AGENT-INDEX.md |
| `push --verify` | Rebuild any broken or missing symlinks |
| `pull` | Scan target for unmanaged doc files and absorb them |
| `pull --strategy wiki/repo` | Resolve conflicts during pull instead of flagging them |
| `detect-drift [--staged]` | Recompute drift by comparing each doc's `SourceCommitID` to HEAD; logs per-doc entries with commit range and changed files |
| `status [--scope X]` | Show pending drift statistics — docs that need attention |
| `eject [--scope X]` | Copy docs back as real files, detaching them from the wiki |
| `clear-flags [--flag X]` | Clear one or all flags; auto-clears flags whose log is empty |
| `add-agent --name <name>` | Create a blank `.md` doc in `.agent-wiki/agents/` (no template) |

## hook-setup stages

| Stage | Flag to skip | What it does |
|-------|-------------|--------------|
| `.agent-wiki/` | (always) | Creates wrapper script, symlinks for flags.json, schema.yaml, AGENT.template.md, instructions.md; creates `agents/` with llm.md, WIKI_UPDATE.md, WIKI_MERGE.md symlinks. Adds to .gitignore. |
| pre-commit | `--no-pre-commit` | Logs changed source files to drift.jsonl before each commit. Non-blocking. |
| post-checkout | `--no-post-checkout` | Runs `push` after checkout to create missing docs and symlinks. |
| skip-worktree | `--no-skip-worktree` | Marks doc symlinks so git never shows them as changes. |

## Key invariants

- Always run `agent-wiki` from the wiki root directory (`config.json` must be present).
- Doc symlinks in the target repo are pointers — `docs/<path>/<doc>` in the wiki is the source of truth.
- `schema.yaml` is the source of truth for which paths are managed.
- Files in `.agent-wiki/` and `.agent-wiki/agents/` are symlinks — editing them edits the wiki directly. Never copy them.
- `instructions.md`, `WIKI_UPDATE.md`, and `WIKI_MERGE.md` are user-owned — they are never overwritten after first creation.
- Files added via `add-agent` are plain files in the target repo, not symlinks — they are not managed by the wiki.
