# WIKI_MERGE — Conflict Resolution Guide

## When a conflict exists

Check `.agent-wiki/flags.json`. If `multiple_versions` is set, both a wiki-managed doc and
an unmanaged real file exist at the same path in the target repo.

Read `logs/conflict.jsonl` to find the affected paths. Each entry contains:
- `rel_path` — the schema path (e.g. `src/payments`)
- `wiki_doc` — absolute path to the canonical doc in the wiki
- `repo_file` — absolute path to the unmanaged real file in the target repo

## Resolution steps

**Step 1 — Assess the git history of both files**

Run `git log --follow -5 --date=short -- <file>` on each version (using their respective
repo roots) to understand:
- Which version is more recent
- Whether they diverged on separate branches (both may be relevant) or one is simply outdated

**Step 2 — Evaluate template adherence**

Open `.agent-wiki/AGENT.template.md`. Compare both versions against it:
- Which version more closely follows the required structure?
- Which follows the quality rules (terse, no filler, agent-focused)?

The version with stronger template adherence is the **preferred base**.

**Step 3 — Merge**

- Use the preferred base as the structural foundation.
- Incorporate unique, non-redundant concepts from the other version.
- Resolve contradictions in favor of the more recent or more specific information.
- Do not duplicate content. Do not add padding.
- Preserve the `<!-- agent-wiki-meta` block at the bottom exactly as-is.

Write the merged result to the **wiki doc** path (not the repo file).

**Step 4 — Replace the repo file with a symlink**

Once the wiki doc contains the merged content, replace the unmanaged repo file:
```bash
rm <repo_file>
.agent-wiki/wiki push --verify
```
`push --verify` recreates the symlink from the wiki doc to the repo path.

**Step 5 — Clear the flag**

```bash
.agent-wiki/wiki clear-flags --flag multiple_versions
```
`clear-flags` auto-clears `multiple_versions` if `conflict.jsonl` is now empty.

## Choosing wiki vs. repo

| Situation | Choose |
|-----------|--------|
| Wiki doc is newer and well-structured | wiki as base |
| Repo file has recent work not in the wiki (separate branch) | repo as base, pull wiki concepts in |
| Both are roughly equal | whichever follows the template more closely |
| One is a placeholder | the other, unconditionally |
