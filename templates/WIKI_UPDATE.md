# WIKI_UPDATE — Documentation Update Guide

## When to update

Check `.agent-wiki/logs/flags.json` before any doc work.

- `drift_detected` — source files changed since the doc was last reviewed; see `drift.jsonl`
- `new_entry` — a placeholder doc exists with no real content; see `new-entry.jsonl`

Run `agent-wiki status` (or `.agent-wiki/wiki status`) for a summary of which docs are affected and how many files changed under each.

## How to detect drift for a specific doc

Every managed doc has a metadata header at the top:

```
<!-- agent-wiki
Check .agent-wiki/flags.json before starting doc work.
LLM Guide: .agent-wiki/agents/llm.md
Wiki Index: .agent-wiki/AGENT-INDEX.md

Location: src/payments/CLAUDE.md
LastTouchedBy: agent-wiki push
ChangeDate: 2026-05-05
SourceCommitID: def5678
-->
```

`SourceCommitID` is the target repo commit the doc was last reviewed against. To see exactly what changed since then:

```bash
git diff <SourceCommitID>..HEAD -- <path>/
```

For example:
```bash
git diff def5678..HEAD -- src/payments/
```

The `drift.jsonl` log pre-computes this for you — each entry includes `from_commit`, `to_commit`, and `changed_files` so you can run the diff directly without reading the header manually.

## How to update a doc

1. **Read the current doc** at the symlink path (e.g. `src/payments/CLAUDE.md`) or at `.agent-wiki/docs/<path>/<doc>` directly. They are the same file.

2. **Run the git diff** for this doc's path using the commit range from the header or `drift.jsonl`. Read the changed files and identify what actually changed.

3. **Ask: does anything in the doc need to change?** See "What to look for" below. If nothing changed that affects the doc — stop here and just clear the flag.

4. **Check the template** at `.agent-wiki/templates/AGENT.template.md` — every doc should follow this structure.

5. **Check the house rules** at `.agent-wiki/templates/instructions.md` for project-specific writing conventions.

6. **Edit the doc directly** via the symlink path. Changes are immediately live in the wiki. Follow these rules:
   - Write for an LLM agent, not a human reader. Be terse.
   - No padding, no filler. Omit anything self-evident from well-named code.
   - Prefer present tense, active voice, concrete nouns.
   - Document anything novel, proprietary, or non-obvious.
   - Do not duplicate content from ancestor doc files — they own their scope.
   - Do not edit or remove the `<!-- agent-wiki` header block at the top.

7. **Clear the flag** when all drifted docs are resolved:
   ```
   agent-wiki clear-flags --flag drift_detected
   ```
   This stamps `SourceCommitID = HEAD` on every doc that had drift, resetting the baseline. `clear-flags` auto-clears a flag if its backing log is already empty.

## What to look for

When diffing source files against a doc, ask:

- Did the public interface (functions, exports, config keys) change?
- Did any invariants, contracts, or error-handling patterns change?
- Are there new or deleted files the doc's Key Files table should reflect?
- Did a naming convention or pattern change that the doc states?
- Is anything the doc currently says wrong or misleading?

If none of the above apply — the doc is still accurate. No edit needed.

## Full review (ignore diff)

If instructed to do a **full review** — phrases like "ignore diff", "check against all time", "review everything", or "full check" — skip the `SourceCommitID` workflow entirely. Instead:

1. Read all source files currently under the doc's path (scan the directory).
2. Read the current doc in full.
3. Compare holistically: does the doc accurately describe the code as it exists today?
4. Apply the same "what to look for" criteria against the entire codebase under that path.

Use this when:
- The doc's baseline is suspect (recently absorbed, never properly reviewed)
- `SourceCommitID` is missing or very old
- The user explicitly requests it

After a full review, clear the flag normally — `clear-flags` will stamp `SourceCommitID = HEAD`.

## Doc placement rules

- Each doc covers only code **at or below** its path.
- Place content at the **highest level where it still applies exclusively**.
- Parent docs cover: repo layout, tech stack, global conventions, shared interfaces.
- Sub-docs cover module-specific detail; do not repeat what a parent already states.
