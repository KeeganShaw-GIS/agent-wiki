# agent-wiki — Quick Reference

## Install

```bash
cargo install agent-wiki
```

Prebuilt binaries for macOS, Linux, and Windows are available on the releases page.

## Quickstart

```bash
# Run from inside the target repo — no separate wiki directory needed
cd /path/to/your-repo
agent-wiki init

# (Optional) push the wiki history to a remote for backup + recovery
cd .agent-wiki && git remote add origin <url> && git push -u origin main && cd ..

# Edit .agent-wiki/schema.yaml to promote paths to doc nodes (append +), then:
agent-wiki push    # creates placeholder docs + symlinks
```

## Create a new documented path

1. Edit `.agent-wiki/schema.yaml` — add the path with `+` (e.g. `frontend/payments+:`)
2. Run `agent-wiki push` — creates placeholder doc + symlink, logs to `new-entry.jsonl`
3. Populate the new doc manually
4. Run `agent-wiki clear-flags --flag new_entry` when done

## Commands

| Command | What it does |
|---------|-------------|
| `init [--doc-filename X] [--wiki-remote <url>]` | One-time setup: `git init .agent-wiki/`, absorb existing doc files, create docs + symlinks, install hooks. Use `--no-detect-target-docs` or `--no-hooks` to skip steps. |
| `hook-setup` | (Re)install `.agent-wiki/wiki` wrapper + git hooks. Called by `init`; run manually to re-install or adjust. |
| `push [--verify]` | Reconcile schema ↔ docs ↔ symlinks. `--verify` repairs broken/missing symlinks only. |
| `pull [--strategy repo\|wiki\|skip]` | Scan target repo for unmanaged doc files and absorb them. |
| `detect-drift [--staged]` | Recompute drift from SourceCommitIDs. Called automatically by pre-commit hook. |
| `status [--scope X]` | Show which docs need attention and why. |
| `eject [--scope X] [--purge]` | Copy docs back as real files, detach from wiki. `--purge` removes `.agent-wiki/` entirely. |
| `clear-flags [--flag X]` | Clear one or all flags; stamps SourceCommitID when clearing drift. |

## Checking for drift

```bash
agent-wiki status           # drift + new-entry summary
```

For each flagged doc:
1. Read `drift.jsonl` — each entry has `from_commit`, `to_commit`, and `changed_files`.
2. Run `git diff <from_commit>..<to_commit> -- <path>/` to see what changed.
3. Update the doc if needed (symlink path = `.agent-wiki/docs/<path>/<doc>`).
4. When all docs are resolved: `agent-wiki clear-flags --flag drift_detected`

Full update guide: `.agent-wiki/agents/WIKI_UPDATE.md`

## Running from the target repo

After `hook-setup`, use the wrapper:

```bash
.agent-wiki/wiki push
.agent-wiki/wiki status
```

The wrapper calls `agent-wiki` from `PATH` — no hardcoded paths.

## Recovery

```bash
git clone <wiki-remote> .agent-wiki/
agent-wiki push --verify    # restores all symlinks
```
