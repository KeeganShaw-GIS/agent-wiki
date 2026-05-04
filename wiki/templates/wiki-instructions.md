# agent-wiki — Quick Reference

## Install

```bash
pipx install git+https://github.com/<you>/agent-wiki.git

# From a local clone (or to update):
pipx install /path/to/agent-wiki --force
```

## Quickstart

```bash
mkdir my-project-wiki && cd my-project-wiki
git init
agent-wiki init --repo-path /path/to/repo
# Edit schema.yaml to promote paths to doc nodes (append +), then:
agent-wiki push    # creates placeholder docs + symlinks
```

## Create a new doc

1. Edit `schema.yaml` — add the path with `+` (e.g. `frontend/payments+:`)
2. Run `push` — creates placeholder doc + symlink, logs to `new-entry.jsonl`
3. Populate the new doc manually

## Commands

| Command | What it does |
|---------|-------------|
| `init --repo-path <path>` | One-time setup: save config, absorb existing doc files, create docs + symlinks, install hooks. Use `--doc-filename`, `--no-detect-target-docs`, or `--no-hooks` to adjust. |
| `hook-setup` | Drop `.agent-wiki/` wrapper + install git hooks in the target repo. Called by init; run manually to re-install or adjust flags. |
| `push` | Reconcile schema ↔ docs ↔ symlinks. Logs new entries to new-entry.jsonl. |
| `pull` | Scan target repo for unmanaged doc files and absorb them into the wiki. |
| `detect-drift [--staged]` | Log changed source files to drift.jsonl. Called automatically by the pre-commit hook. |
| `status [--scope X]` | Show pending drift statistics — which docs need attention and why. |
| `eject [--scope X]` | Copy docs back into the target repo as real files, remove symlinks — wiki stops tracking those paths. |

## Checking for drift

Run `status` to see which docs are behind their source files:

```bash
agent-wiki status           # drift + new-entry logs
agent-wiki status --scope diff    # scope to current changes only
```

Each line shows a doc, why it's flagged (`drift` / `new-file`), and how many source files changed under it. For each flagged doc:

1. Read `drift.jsonl` — each entry has `from_commit`, `to_commit`, and `changed_files`.
2. Run `git diff <from_commit>..<to_commit> -- <path>/` in the target repo to see exactly what changed.
3. Ask: did any interfaces, invariants, patterns, or key facts change?
4. If yes → update the doc. If no → clear the flag without editing.

When done: `clear-flags --flag drift_detected` stamps `SourceCommitID=HEAD` on each drifted doc, resetting the baseline.

Full step-by-step update guide: `.agent-wiki/agents/WIKI_UPDATE.md`

## Running from the target repo

After `hook-setup`, use the wrapper dropped in the target repo:

```bash
.agent-wiki/wiki push
.agent-wiki/wiki status
```
