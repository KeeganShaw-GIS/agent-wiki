# agent-wiki

A documentation wiki manager for LLM agents. Maintains `CLAUDE.md`, `AGENTS.md`, or similar agent instruction files for a target git repo in a separate wiki repo and symlinks them in — so your LLM agent loads the right docs at the right path depth automatically, without polluting the target's git history.

Works with any agent that respects per-directory instruction files: **Claude Code** (`CLAUDE.md`), **OpenAI Codex** (`AGENTS.md`), or any custom filename. Also generates an `AGENT-INDEX.md` in `.agent-wiki/` as a navigation hub for tools like Cursor and GitHub Copilot that don't support hierarchical doc loading.

## Install

**macOS / Linux — standalone binary (no Python required):**

```bash
curl -fsSL https://raw.githubusercontent.com/KeeganShaw-GIS/agent-wiki/main/install.sh | bash
```

**Any platform — pip (requires Python 3.11+):**

```bash
# Latest
pipx install git+https://github.com/KeeganShaw-GIS/agent-wiki.git

# Specific version
pipx install git+https://github.com/KeeganShaw-GIS/agent-wiki.git@v0.1.0
```

---

## Quick start

```bash
# 1. Init — create config, absorb existing docs, install hooks
mkdir my-project-wiki && cd my-project-wiki
git init
agent-wiki init --repo-path /path/to/your/repo

# 2. Edit schema.yaml to promote paths to doc nodes (append +), then:
agent-wiki push    # create placeholder docs + symlinks

# 3. Done — symlinks are live, populate docs manually
```

Every command must be run from the wiki root (where `config.json` lives).

### Ejecting

`eject` copies each wiki doc back into the target repo as a real file, removes the symlinks, and stops the wiki from tracking those paths. After ejecting, the target repo owns its doc files again — the wiki no longer manages or updates them.

```bash
agent-wiki eject           # eject all managed paths
agent-wiki eject --scope frontend/survey  # eject a single path
```

---

## Config files

### `schema.yaml`

Defines which paths in the target repo have managed doc files. Generated automatically on `init` from the target repo's top-level directories — promote paths to doc nodes by appending `+`.

```yaml
# + = managed doc node (<doc> in docs/ + symlink in target)
# ~ = untracked (real file stays in target, wiki ignores it)
# (no suffix) = structural container only, no doc
root+:
  frontend+:
    admin+:
    survey+:
  server+:
  local-docs:
    as-built~:
```

### `config.json`

Set by `init`, gitignored. Stores the target repo path and options.

```json
{
  "repo_path": "/path/to/your/repo",
  "repo_name": "my-repo",
  "skip_worktree": true,
  "doc_filename": "CLAUDE.md"
}
```

`doc_filename` is set during `init` (prompted interactively or via `--doc-filename`). Common values: `CLAUDE.md` (Claude Code), `AGENTS.md` (OpenAI Codex).

---

## Document generation

Wiki docs live in `docs/`, mirroring the target repo's path structure:

```
docs/
├── <doc>                   ← target repo root
├── frontend/
│   ├── <doc>               ← target frontend/
│   └── survey/
│       └── <doc>           ← target frontend/survey/
└── server/
    └── <doc>
```
(`<doc>` = your configured `doc_filename`, e.g. `CLAUDE.md` or `AGENTS.md`)

### Output → symlinks + AGENT-INDEX.md

For each `+` node in `schema.yaml`, `push` creates a symlink in the target repo pointing back to the wiki doc:

```
target/frontend/survey/AGENTS.md  →  ../../../my-wiki/docs/frontend/survey/AGENTS.md
```

The **root symlink** (`CLAUDE.md` or `AGENTS.md` at the target repo root) is special — it points to `.agent-wiki/AGENT-INDEX.md`, a generated navigation hub listing the full doc tree and links to agent resources. Per-directory symlinks work as normal for hierarchy-aware tools; the index serves non-hierarchy tools.

`push` also creates **mirror symlinks** inside `.agent-wiki/` that mirror the full doc tree, so all docs are accessible from within the gitignored directory.

Symlinks are marked `skip-worktree` in the target repo so git never sees them as changes.

### `templates/instructions.md`

Created on `init`. House rules for writing doc content — edit it to control doc style and structure. Never overwritten after first creation.

### `templates/AGENT.template.md`

Placeholder written by `push` when a new doc is created. Contains a "not yet populated" banner. Populate docs manually after running `push`.

---

> **Key:** `D` Deterministic

## Commands

---

### `init` `D`

One-time setup. Run from an empty wiki directory. Fully deterministic — no LLM is invoked. After init, populate placeholder docs manually.

```bash
agent-wiki init --repo-path /path/to/repo
# Prompts: which doc filename? (CLAUDE.md / AGENTS.md / custom)

# Skip the interactive prompt — set filename directly
agent-wiki init --repo-path /path/to/repo --doc-filename AGENTS.md

# Skip absorbing existing doc files from the target
agent-wiki init --repo-path /path/to/repo --no-detect-target-docs

# Skip installing git hooks
agent-wiki init --repo-path /path/to/repo --no-hooks
```

`init` runs these steps in order:
1. Prompts for `doc_filename` (or uses `--doc-filename`), saves `config.json` `D`
2. Generates `llm.md` and `templates/instructions.md` `D`
3. Generates `schema.yaml` from the target repo's top-level directories `D`
4. Absorbs any existing doc files from the target via `pull` (skip with `--no-detect-target-docs`) `D`
5. Runs `push` to create docs and symlinks `D`
6. Runs `hook-setup` to install git hooks (skip with `--no-hooks`) `D`
7. Prints any new-entry paths that need manual doc population

---

### `hook-setup` `D`

Installs git hooks and the `.agent-wiki/` wrapper in the target repo. Called automatically by `init`; run manually to re-install or adjust stages. Fully deterministic — no LLM.

Hooks locate the wiki automatically by resolving the root doc symlink — no separate config file needed.

```bash
agent-wiki hook-setup

# Skip individual stages
agent-wiki hook-setup --no-pre-commit
agent-wiki hook-setup --no-post-checkout
agent-wiki hook-setup --no-skip-worktree
```

---

### `pull` `D`

Scans the target repo for unmanaged real doc files (not symlinks), absorbs their content into `docs/`, replaces them with symlinks, and adds them to `schema.yaml`. Logs each absorbed path to `logs/new-entry.jsonl`.

```bash
agent-wiki pull
```

Use this when cloning a target repo that already has doc files, or when someone added one manually without going through the wiki.

---

### `push` `D`

Reconciles `schema.yaml` ↔ `docs/` ↔ symlinks in the target. Run after editing `schema.yaml`. New docs are written as deterministic placeholders and logged to `logs/new-entry.jsonl` — no LLM.

```bash
# Sync schema with docs and symlinks
agent-wiki push

# Also absorb unmanaged doc files from the target
agent-wiki push --detect-target-docs

# Rebuild only broken or missing symlinks
agent-wiki push --verify
```

---

### `detect-drift` `D`

Computes drift by comparing each doc's `SourceCommitID` footer against `HEAD` in the target repo. For each doc with changes, logs a `drift.jsonl` entry containing the commit range and changed files — enough to run `git diff <from>..<to> -- <path>/` directly. Idempotent: re-running overwrites stale entries rather than appending.

Called automatically by the pre-commit hook (`--staged`). Safe to run manually at any time, including on repos that never had the hook installed.

```bash
agent-wiki detect-drift           # recompute all drift from SourceCommitIDs
agent-wiki detect-drift --staged  # narrow to staged files only
```

---

### `status` `D`

Shows pending drift statistics — which docs need attention and why. Reads `drift.jsonl` and `new-entry.jsonl`; no LLM involved.

```bash
# Show all pending docs from drift + new-entry logs
agent-wiki status

# Show docs affected by a specific path, ref, or diff
agent-wiki status --scope frontend/survey
agent-wiki status --scope diff
agent-wiki status --scope staged
```

---

### `eject` `D`

Copies each managed doc file back into the target repo as a real file and removes the symlinks. The target repo owns its docs again — the wiki stops tracking and updating those paths. Wiki docs in `docs/` are preserved untouched. Run `push` to re-attach.

```bash
# Eject all managed paths
agent-wiki eject

# Eject a single path
agent-wiki eject --scope frontend/survey
```

---

### `add-agent` `D`

Creates a blank `.md` file in `.agent-wiki/agents/` of the target repo. Use this to add custom agent guidance docs that live alongside the standard `llm.md`, `WIKI_UPDATE.md`, and `WIKI_MERGE.md` symlinks.

```bash
agent-wiki add-agent --name researcher
# creates .agent-wiki/agents/researcher.md  (empty)
```

---

## Hooks

All hooks are **fully deterministic** — no LLM is ever invoked by a hook. The drift log they build up is visible via `agent-wiki status`.

| Hook | Trigger | What it runs | `D/🤖` |
|------|---------|-------------|--------|
| `pre-commit` | Before every commit | `detect-drift --staged` | `D` |
| `post-checkout` | After checkout / clone | `push` | `D` |

### `hook-setup` stages

Run automatically by `init` (or manually via `agent-wiki hook-setup`). Each hook stage can be skipped independently. The `.agent-wiki/` directory is always created — hooks depend on it.

Hooks call `.agent-wiki/wiki` in the target repo. The wrapper resolves the wiki root from `.agent-wiki/wiki-path` — no hardcoded paths, no separate config file needed.

| Stage | Flag to skip | `D/🤖` | What it does |
|-------|-------------|--------|-------------|
| `.agent-wiki/` | (always) | `D` | Creates `.agent-wiki/wiki` wrapper script, operational symlinks (flags.json, schema.yaml, AGENT.template.md, instructions.md), and the `agents/` subdirectory with llm.md, WIKI_UPDATE.md, WIKI_MERGE.md symlinks. Adds `.agent-wiki` to `.gitignore`. |
| `pre-commit` | `--no-pre-commit` | `D` | Installs `.git/hooks/pre-commit`. Before each commit, runs `detect-drift --staged` to recompute drift for staged files. Always exits 0 — never blocks a commit. |
| `post-checkout` | `--no-post-checkout` | `D` | Installs `.git/hooks/post-checkout`. After checkout or clone, runs `push` to create any missing docs and symlinks. New docs get a placeholder template and are logged to `new-entry.jsonl`. |
| `skip-worktree` | `--no-skip-worktree` | `D` | Marks every managed doc symlink `skip-worktree` so git never shows them as unstaged changes. Skip if you use sparse checkout or a tool that resets index flags. |

---

## Layout

### Wiki repo

```
my-project-wiki/
├── schema.yaml              # Source of truth for which paths are managed
├── config.json              # Target repo path — gitignored
├── llm.md                   # LLM reference for working in this wiki
├── docs/                    # All documentation; mirrors target repo structure
│   └── <path>/<doc>
├── templates/
│   ├── AGENT.template.md   # Placeholder written when push creates a new doc
│   ├── instructions.md      # House rules for writing doc content
│   ├── WIKI_UPDATE.md       # Step-by-step guide for updating docs (user-editable)
│   └── WIKI_MERGE.md        # Step-by-step guide for resolving conflicts (user-editable)
├── logs/
│   ├── drift.jsonl          # Per-doc drift entries with commit range + changed files
│   ├── new-entry.jsonl      # New schema entries pending documentation
│   └── sync.jsonl           # Permanent sync history
└── scripts/
    └── wiki.py              # Backward-compat shim for git hooks
```

### Target repo (after `hook-setup`)

```
my-target-repo/
├── <doc>                    # Symlink → .agent-wiki/AGENT-INDEX.md  (root entry point)
├── <path>/<doc>             # Symlinks for each managed path → wiki docs
└── .agent-wiki/            # Gitignored — created by hook-setup
    ├── wiki                 # Wrapper: runs agent-wiki from inside the target repo
    ├── wiki-path            # Path to the wiki root (read by wrapper)
    ├── flags.json           # Symlink → <wiki>/logs/flags.json
    ├── schema.yaml          # Symlink → <wiki>/schema.yaml
    ├── AGENT.template.md   # Symlink → <wiki>/templates/AGENT.template.md
    ├── instructions.md      # Symlink → <wiki>/templates/instructions.md
    └── agents/              # LLM guidance docs
        ├── llm.md           # Symlink → <wiki>/llm.md
        ├── WIKI_UPDATE.md   # Symlink → <wiki>/templates/WIKI_UPDATE.md
        ├── WIKI_MERGE.md    # Symlink → <wiki>/templates/WIKI_MERGE.md
        └── <name>.md        # User-added agent docs (via `add-agent --name <name>`)
```

Developers can run any wiki command directly from the target repo:

```bash
.agent-wiki/wiki push
.agent-wiki/wiki status
```

LLM agents working in the target repo can do the same — they see the doc symlinks and can run wiki commands through `.agent-wiki/wiki`.

### Doc metadata footer

Every managed doc file gets a metadata block appended automatically:

```
<!-- agent-wiki-meta
Location: frontend/survey/AGENTS.md
LastTouchedBy: agent-wiki push
ChangeDate: 2026-05-01
WikiCommitID: abc1234
SourceCommitID: def5678
-->
```

`SourceCommitID` is the target repo commit the doc was last reviewed against. `detect-drift` computes `git diff <SourceCommitID>..HEAD -- <path>/` to find what changed. `clear-flags --flag drift_detected` stamps it to the current HEAD. Stripped when you `eject`.
