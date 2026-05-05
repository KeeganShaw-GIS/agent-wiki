# agent-wiki

A documentation wiki manager for LLM agents. Keeps `CLAUDE.md`, `AGENTS.md`, or similar per-directory instruction files on their **own git history** — separate from your code — and symlinks them into the target repo so every LLM agent loads the right docs at the right path depth automatically.

Works with any agent that respects per-directory instruction files: **Claude Code** (`CLAUDE.md`), **OpenAI Codex** (`AGENTS.md`), or any custom filename. Also generates an `AGENT-INDEX.md` inside `.agent-wiki/` as a navigation hub for tools like Cursor and GitHub Copilot that don't support hierarchical doc loading.

## Why nested git repo?

Docs live in `.agent-wiki/` inside the target repo — a nested git repo with its own remote. The target repo gitignores `.agent-wiki/` entirely so docs never pollute code reviews or the code history.

If `.agent-wiki/` is ever lost, recovery is one command:

```bash
git clone <wiki-remote> .agent-wiki/
agent-wiki push --verify     # restores all symlinks
```

---

## Install

**Homebrew / cargo (macOS, Linux):**

```bash
cargo install agent-wiki
```

**Prebuilt binaries** are available on the [releases page](https://github.com/KeeganShaw-GIS/agent-wiki/releases) for macOS (arm64/x86), Linux (musl), and Windows.

---

## Quick start

```bash
# 1. From inside your target repo — no separate wiki dir needed
cd /path/to/your-repo
agent-wiki init

# 2. (Optional) add a remote so the wiki history can be pushed/pulled
cd .agent-wiki && git remote add origin <url> && git push -u origin main

# 3. Edit .agent-wiki/schema.yaml to promote paths to doc nodes (append +), then:
agent-wiki push    # create placeholder docs + symlinks

# 4. Populate the placeholder docs manually, then commit inside .agent-wiki/
```

Run `agent-wiki` from anywhere inside the target repo — it walks up to find `.agent-wiki/schema.yaml`.

---

## Config

### `schema.yaml`

Lives at `.agent-wiki/schema.yaml`. Defines which paths in the target repo have managed doc files. Committed to the wiki git history.

```yaml
# + = managed doc node (doc in .agent-wiki/docs/ + symlink in target repo)
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

Lives at `.agent-wiki/config.json`. Committed to the wiki git history.

```json
{
  "doc_filename": "CLAUDE.md"
}
```

`doc_filename` is set during `init` via `--doc-filename`. Common values: `CLAUDE.md` (Claude Code), `AGENTS.md` (OpenAI Codex).

---

## Layout

### Inside the target repo

```
your-repo/
├── .gitignore                   # includes .agent-wiki/
├── src/
│   └── CLAUDE.md                # symlink → ../.agent-wiki/docs/src/CLAUDE.md
├── CLAUDE.md                    # symlink → .agent-wiki/docs/CLAUDE.md
└── .agent-wiki/                 # nested git repo (own history, own remote)
    ├── .git/
    ├── .gitignore               # ignores: logs/ symlinks/ agents/
    ├── schema.yaml              # committed — source of truth
    ├── config.json              # committed — doc_filename
    ├── docs/                    # committed — all documentation
    │   ├── CLAUDE.md
    │   └── src/CLAUDE.md
    ├── templates/               # committed — customisable templates
    │   ├── AGENT.template.md
    │   ├── instructions.md
    │   ├── WIKI_UPDATE.md
    │   └── WIKI_MERGE.md
    ├── llm.md                   # committed — LLM agent guidance
    ├── AGENT-INDEX.md           # regenerated — navigation hub
    ├── wiki                     # wrapper script: exec agent-wiki "$@"
    ├── logs/                    # gitignored — operational state
    │   ├── flags.json
    │   ├── drift.jsonl
    │   ├── new-entry.jsonl
    │   └── conflict.jsonl
    ├── symlinks/                # gitignored — flat mirror, regenerated
    └── agents/                  # gitignored — symlinks to templates
        ├── llm.md
        ├── WIKI_UPDATE.md
        └── WIKI_MERGE.md
```

LLM agents and developers can run any wiki command using the wrapper:

```bash
.agent-wiki/wiki push
.agent-wiki/wiki status
```

---

## Doc metadata header

Every managed doc has a header block written at the top automatically:

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

`SourceCommitID` is the target repo commit the doc was last reviewed against. `detect-drift` computes `git diff <SourceCommitID>..HEAD -- <path>/` to find what changed. `clear-flags` stamps it to current HEAD when drift is cleared. The block is stripped when you `eject`.

---

> **Key:** `D` Deterministic — no LLM invoked

## Commands

---

### `init` `D`

One-time setup. Run from the target repo root (or anywhere inside it). Fully deterministic.

```bash
agent-wiki init

# Choose a doc filename other than CLAUDE.md
agent-wiki init --doc-filename AGENTS.md

# Add a remote for the wiki git repo (backup + recovery)
agent-wiki init --wiki-remote git@github.com:you/your-repo-wiki.git

# Skip absorbing existing doc files
agent-wiki init --no-detect-target-docs

# Skip installing git hooks
agent-wiki init --no-hooks
```

`init` steps:
1. `git init .agent-wiki/` — nested git repo with its own history
2. Writes `config.json`, `schema.yaml`, `.agent-wiki/.gitignore`, templates, `llm.md`, `logs/flags.json`
3. Adds `.agent-wiki` to the target repo's `.gitignore`
4. Absorbs any existing doc files via `pull` (skip with `--no-detect-target-docs`)
5. Runs `push` to create docs and symlinks
6. Installs git hooks via `hook-setup` (skip with `--no-hooks`)

---

### `push` `D`

Reconciles `schema.yaml` ↔ `docs/` ↔ symlinks in the target. Run after editing `schema.yaml`. New docs are written as deterministic placeholders and logged to `new-entry.jsonl`.

```bash
agent-wiki push

# Rebuild broken or missing symlinks only
agent-wiki push --verify
```

---

### `pull` `D`

Scans the target repo for unmanaged real doc files (not symlinks), absorbs their content into `docs/`, replaces them with symlinks, and adds them to `schema.yaml`.

```bash
agent-wiki pull                      # default: repo wins on conflict (backs up wiki doc)
agent-wiki pull --strategy wiki      # wiki wins: replace repo file with symlink
agent-wiki pull --strategy skip      # flag conflict without resolving
```

---

### `detect-drift` `D`

Computes drift by comparing each doc's `SourceCommitID` against `HEAD`. Logs a `drift.jsonl` entry per drifted doc containing the commit range and changed files. Idempotent — re-running overwrites stale entries.

Called automatically by the pre-commit hook (`--staged`). Safe to run manually at any time.

```bash
agent-wiki detect-drift           # all docs
agent-wiki detect-drift --staged  # staged files only (pre-commit hook mode)
```

---

### `status` `D`

Shows pending drift statistics — which docs need attention and why.

```bash
agent-wiki status
agent-wiki status --scope frontend/survey
agent-wiki status --scope diff
agent-wiki status --scope staged
```

---

### `eject` `D`

Copies each managed doc back into the target repo as a real file, strips the wiki header, and removes the symlink. The target repo owns its docs again. Wiki docs in `docs/` are preserved in git history.

```bash
agent-wiki eject                       # eject all managed paths
agent-wiki eject --scope frontend      # eject a single path
agent-wiki eject --purge               # eject all + remove .agent-wiki/ entirely
```

---

### `clear-flags` `D`

Clears one or all status flags. Auto-clears flags whose backing log is empty. When clearing `drift_detected`, stamps `SourceCommitID = HEAD` on each drifted doc.

```bash
agent-wiki clear-flags                        # clear all
agent-wiki clear-flags --flag drift_detected  # clear specific flag
agent-wiki clear-flags --flag new_entry       # repeatable: --flag a --flag b
```

---

### `hook-setup` `D`

Installs git hooks and the `.agent-wiki/wiki` wrapper. Called automatically by `init`; run manually to re-install.

```bash
agent-wiki hook-setup
agent-wiki hook-setup --no-pre-commit
agent-wiki hook-setup --no-post-checkout
```

---

## Hooks

All hooks are **fully deterministic** — no LLM is ever invoked.

| Hook | Trigger | What it runs |
|------|---------|--------------|
| `pre-commit` | Before every commit | `detect-drift --staged` |
| `post-checkout` | After checkout / clone | `push` |

Hooks call `.agent-wiki/wiki` in the target repo. The wrapper resolves `agent-wiki` from `PATH` — no hardcoded paths.

---

## Recovery

```bash
# If .agent-wiki/ was deleted without ejecting:
git clone <wiki-remote> .agent-wiki/
agent-wiki push --verify    # restores all symlinks
```

Without a remote, recovery requires a local backup or re-init. Add a remote during `init` with `--wiki-remote <url>` or afterwards via `cd .agent-wiki && git remote add origin <url>`.
