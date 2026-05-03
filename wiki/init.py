"""init: One-time setup — record target repo path, create docs and symlinks, install hooks."""

from pathlib import Path

from .lib import (
    CONFIG_FILE, INSTRUCTIONS_FILE, MERGE_PROMPT_FILE, SCHEMA_FILE,
    UPDATE_PROMPT_EXISTING_FILE, UPDATE_PROMPT_NEW_FILE, WIKI_ROOT,
    save_config, save_schema,
)

LLM_MD_FILE = WIKI_ROOT / "llm.md"

_LLM_MD = """\
# claude-wiki — LLM Reference

This directory is a **claude-wiki** wiki root. It holds CLAUDE.md documentation for a target
git repo and symlinks them in so Claude Code loads them automatically at the correct path depth.

## Directory layout

```
<wiki-root>/
├── schema.yaml          # Which paths in the target repo are documented
├── config.json          # Target repo path — gitignored, set by `init`
├── docs/                # All documentation; mirrors target repo structure
│   └── <path>/CLAUDE.md
├── templates/
│   ├── CLAUDE.template.md   # Placeholder written when a new doc is created
│   └── instructions.md      # House rules injected into every update prompt
├── logs/
│   ├── drift.jsonl      # Source files changed since last sync (cleared on sync)
│   ├── new-entry.jsonl  # New schema entries pending update (cleared on update)
│   ├── flags.json       # Current wiki status flags (see below)
│   └── sync.jsonl       # Permanent update history
└── llm.md               # This file

<target-repo>/
├── CLAUDE.md            # Symlink → <wiki>/docs/CLAUDE.md
├── <path>/CLAUDE.md     # Symlinks for each managed path
└── .claude-wiki/        # Gitignored — created by `hook-setup`
    ├── wiki             # Wrapper script: runs claude-wiki from within the target repo
    ├── wiki-path        # Path to this wiki root (read by wrapper)
    ├── llm.md           # Symlink → <wiki>/llm.md
    └── flags.json       # Symlink → <wiki>/logs/flags.json
```

## flags.json

`logs/flags.json` (symlinked to `.claude-wiki/flags.json` in the target repo) reflects the current wiki status. Check it before starting any task that involves documentation.

| Flag | Meaning | Action |
|------|---------|--------|
| `new_entry` | New schema paths were added; placeholder docs exist | Run `update` to generate content |
| `drift_detected` | Source files changed since last update | Run `update` to update affected docs |
| `docs_out_of_sync` | Broken/missing symlinks were found and repaired | Run `update` — repaired docs may have placeholder content |

Flags are absent (not just `false`) when the condition is clear. A missing key means no action needed for that concern.

Example:
```json
{
  "new_entry": true,
  "drift_detected": true,
  "docs_out_of_sync": {
    "count": 2,
    "paths": ["server/services/payments", "frontend/admin"]
  },
  "last_updated": "2026-05-01T12:00:00Z"
}
```

## schema.yaml

Controls which paths have managed CLAUDE.md files. Three node types:

| Suffix | Meaning |
|--------|---------|
| `+`    | Managed — has a doc in `docs/` and a symlink in the target |
| `~`    | Untracked — real file stays in target, wiki ignores it |
| (none) | Structural — nesting container only, no doc |

`root+` is the sentinel for the repo root (maps to `docs/CLAUDE.md`).

## The symlink mechanic

For each `+` node, a symlink is created in the target repo pointing back to `docs/<path>/CLAUDE.md`
in this wiki. Editing `docs/<path>/CLAUDE.md` here is immediately reflected in the target.
Symlinks are marked `skip-worktree` in the target so git never commits them.

## Adding a new documented path

1. Add the path to `schema.yaml` (append `+` to the key).
2. Run `push` — creates the doc with placeholder content and logs it to `new-entry.jsonl`.
3. Run `update` (no scope) — detects the new-entry log, scans the path for source files, and generates content from scratch.

## Commands

| Command | What it does |
|---------|-------------|
| `init --repo-path <path>` | Save config, absorb existing CLAUDE.md files, create docs + symlinks, install hooks. No LLM. |
| `init --no-detect-target-docs` | Skip absorbing existing CLAUDE.md files |
| `init --no-hooks` | Skip hook-setup |
| `hook-setup` | Create `.claude-wiki/` in target repo + install git hooks (also called by init) |
| `hook-setup --no-pre-commit` | Skip pre-commit hook |
| `hook-setup --no-post-checkout` | Skip post-checkout hook |
| `hook-setup --no-skip-worktree` | Skip marking symlinks skip-worktree |
| `push` | Reconcile schema ↔ docs ↔ symlinks; log new entries to new-entry.jsonl |
| `push --verify` | Rebuild any broken or missing symlinks |
| `push --detect-target-docs` | Scan target for real CLAUDE.md files and absorb them |
| `pull` | Scan target for real CLAUDE.md files and absorb them (standalone) |
| `detect-drift [--staged]` | Log changed source files to drift.jsonl (used by pre-commit hook) |
| `update [--scope X]` | LLM reads source files and updates wiki docs; processes drift + new-entry logs |
| `update --dry-run` | Show what would be updated (scope, kind, source file count, ancestor context) — no LLM |
| `update --no-prompt` | Non-interactive update (automated/CI mode) |
| `eject [--scope X]` | Copy docs back into the target repo as real files, remove symlinks — wiki stops tracking those paths |

## Create a new doc

1. Add the path to `schema.yaml` (append `+` to the key).
2. Run `push` — creates placeholder doc + symlink, logs to `new-entry.jsonl`.
3. Run `update` — LLM scans the path and generates content from scratch.

## hook-setup stages

`hook-setup` is called automatically by `init` (skip with `--no-hooks`).
Each stage can also be run or skipped independently via the `hook-setup` command.

| Stage | Flag to skip | What it does |
|-------|-------------|--------------|
| .claude-wiki/ | (always runs) | Creates `.claude-wiki/` in the target repo with a `wiki` wrapper script and a `llm.md` symlink. Adds `.claude-wiki` to `.gitignore`. Hooks call this wrapper — no separate config needed. |
| pre-commit | `--no-pre-commit` | Installs `.git/hooks/pre-commit`. Before each commit, runs `detect-drift --staged` to log changed source files to `drift.jsonl`. Always exits 0 — never blocks a commit. |
| post-checkout | `--no-post-checkout` | Installs `.git/hooks/post-checkout`. After `git checkout` or clone, runs `push` to create missing docs and symlinks. New docs get a placeholder and are logged to `new-entry.jsonl`. |
| skip-worktree | `--no-skip-worktree` | Runs `git update-index --skip-worktree` on every managed CLAUDE.md symlink so git never shows them as unstaged changes. |

## Scope values (update)

| Value | Meaning |
|-------|---------|
| (none) | drift.jsonl + new-entry.jsonl entries (both cleared after run) |
| `path/to/file` | Single source file |
| `path/to/dir` | All files under that directory |
| `diff` | All staged + unstaged changes |
| `staged` | Staged changes only |
| `<git-ref>` | Files changed in that commit or branch |

## update behavior

- **New doc (placeholder content)**: Claude scans all files under the path and generates documentation from scratch.
- **Existing doc (drift)**: Claude reads only the changed files and updates sections that are wrong or missing.
- When scope is omitted (drift + new-entry mode), both `drift.jsonl` and `new-entry.jsonl` are cleared after the run.
- Interactive mode (`Read,Edit,Write`) allows Claude to propose new schema paths and create new docs.
- `--no-prompt` restricts tools to `Read,Edit` — existing docs only, no new files.

## Update cycle

```
git commit
  └─ pre-commit hook → detect-drift --staged → appends to drift.jsonl

claude-wiki update
  ├─ reads drift.jsonl + new-entry.jsonl
  ├─ LLM updates or generates each doc
  └─ clears drift.jsonl + processed new-entry.jsonl entries
```

## Key invariants

- Always run `claude-wiki` from the wiki root directory (`config.json` must be present).
- Never hand-edit symlinks in the target repo — run `check-paths` instead.
- `docs/<path>/CLAUDE.md` is the source of truth; the symlink in the target is a pointer.
- `instructions.md` is user-owned — never overwrite it after first creation.
- `schema.yaml` is the source of truth for which paths are managed.
"""
from .check_paths import run_push_docs, ensure_root_banner
from .lib import DOCS_ROOT


def _ensure_schema(repo: Path):
    if SCHEMA_FILE.exists():
        print("  [exists]   schema.yaml  (skipped)")
        return

    schema: dict = {"root+": {}}
    save_schema(schema)
    print("  [created]  schema.yaml")


_DEFAULT_INSTRUCTIONS = """\
# Doc Writing Instructions

These rules govern how CLAUDE.md files are written and updated.
Edit this file to match your team's preferences — it is injected into every update run.

## Voice & Density
- Write for an LLM agent, not a human reader. Be terse. Omit what can be inferred from code.
- No padding, no filler. If there is nothing real to say in a section, omit it.
- Prefer present tense, active voice, concrete nouns.

## Sections (include only where applicable)
- **Purpose** — one paragraph on the responsibility of this path.
- **Key Files / Entry Points** — table of the most important files and their role.
- **Patterns & Conventions** — non-obvious patterns an agent needs to follow here.
- **Dependencies / Interfaces** — what this code calls and what calls it.
- **Gotchas** — traps, constraints, or invariants that would surprise a careful reader.

## Placement Rules
- A doc covers only code **at or below** its path.
- Parent docs cover: repo layout, tech stack, global conventions, shared interfaces.
- Sub-docs cover module-specific detail; do not repeat what a parent already states.

## What to Document
- Anything novel, proprietary, or non-obvious.
- Invariants the agent must preserve when editing.
- Naming conventions, error-handling contracts, or auth/security requirements specific to this path.

## What to Omit
- Anything self-evident from well-named code.
- Generic boilerplate that adds no actionable signal.
- Information already documented in an ancestor CLAUDE.md.
"""


_WIKI_INSTRUCTIONS_FILE = WIKI_ROOT / "wiki-instructions.md"

_WIKI_INSTRUCTIONS = """\
# claude-wiki — Quick Reference

## Install

```bash
pipx install git+https://github.com/<you>/claude-wiki.git

# From a local clone (or to update):
pipx install /path/to/claude-wiki --force
```

## Quickstart

```bash
mkdir my-project-wiki && cd my-project-wiki
git init
claude-wiki init --repo-path /path/to/repo
# Edit schema.yaml to promote paths to doc nodes (append +), then:
claude-wiki push    # creates placeholder docs + symlinks
claude-wiki update  # LLM generates content for new entries
```

## Create a new doc

1. Edit `schema.yaml` — add the path with `+` (e.g. `frontend/payments+:`)
2. Run `push` — creates placeholder doc + symlink, logs to `new-entry.jsonl`
3. Run `update` — LLM scans the path and generates content from scratch

## Commands

| Command | What it does |
|---------|-------------|
| `init --repo-path <path>` | One-time setup: save config, absorb existing CLAUDE.md files, create docs + symlinks, install hooks. No LLM. Use `--no-detect-target-docs` or `--no-hooks` to skip steps. |
| `hook-setup` | Drop `.claude-wiki/` wrapper + install git hooks in the target repo. Called by init; run manually to re-install or adjust flags. |
| `push` | Reconcile schema ↔ docs ↔ symlinks. Logs new entries to new-entry.jsonl. |
| `pull` | Scan target repo for unmanaged CLAUDE.md files and absorb them into the wiki. |
| `detect-drift [--staged]` | Log changed source files to drift.jsonl. Called automatically by the pre-commit hook. |
| `update [--scope X]` | LLM updates docs; processes drift + new-entry logs (clears both when no scope). |
| `update --dry-run` | Preview what would be updated: scope type, per-doc kind (drift/new-file/manual), source file count, and ancestor docs that would be passed as context. No LLM. |
| `eject [--scope X]` | Copy docs back into the target repo as real files, remove symlinks — wiki stops tracking those paths. |

## Scope values (update)

| Value | Meaning |
|-------|---------|
| (none) | drift.jsonl + new-entry.jsonl entries (both cleared after run) |
| `path/to/file` | Single source file |
| `path/to/dir` | All files under that directory |
| `diff` | All staged + unstaged changes |
| `staged` | Staged changes only |
| `<git-ref>` | Files changed in that commit or branch |

## Running from the target repo

After `hook-setup`, use the wrapper dropped in the target repo:

```bash
.claude-wiki/wiki push
.claude-wiki/wiki update --scope src/payments
```
"""


def _ensure_wiki_instructions():
    if not _WIKI_INSTRUCTIONS_FILE.exists():
        _WIKI_INSTRUCTIONS_FILE.write_text(_WIKI_INSTRUCTIONS)
        print("  [created]  wiki-instructions.md")
    else:
        print("  [exists]   wiki-instructions.md  (skipped)")


def _ensure_llm_md():
    if not LLM_MD_FILE.exists():
        LLM_MD_FILE.write_text(_LLM_MD)
        print("  [created]  llm.md")
    else:
        print("  [exists]   llm.md  (skipped)")


def _ensure_instructions():
    if not INSTRUCTIONS_FILE.exists():
        INSTRUCTIONS_FILE.parent.mkdir(parents=True, exist_ok=True)
        INSTRUCTIONS_FILE.write_text(_DEFAULT_INSTRUCTIONS)
        print("  [created]  templates/instructions.md  (edit to customize)")
    else:
        print("  [exists]   templates/instructions.md  (skipped — already customized)")


# ── LLM prompt templates ──────────────────────────────────────────────────────
# These are written once on init and can be freely edited. They are loaded at
# runtime, so changes take effect on the next run — no reinstall needed.
#
# Placeholder tokens (filled by Python at runtime):
#   update-prompt-new.md      {wiki_doc}, {file_list}, {ancestor_block}, {interaction_rules}, {instructions_block}
#   update-prompt-existing.md {wiki_doc}, {file_list}, {interaction_rules}, {instructions_block}
#   merge-prompt.md           {wiki_doc}, {repo_file}, {wiki_git_log}, {repo_git_log}, {template_section}, {user_context}

_DEFAULT_UPDATE_PROMPT_NEW = """\
You are maintaining live documentation for a software project.
{instructions_block}
This is a **new documentation file** — it has not been populated yet.
  {wiki_doc}

Source files at this path:
{file_list}
{ancestor_block}
Instructions:
1. Read all source files listed above.
2. Write comprehensive documentation from scratch, replacing the placeholder content entirely.
3. Do not duplicate content already covered in the ancestor docs above — those files own their scope.
4. Do not add padding or filler. Only write what is genuinely useful for an LLM agent
   working in this codebase.
5. Document anything novel, proprietary, or non-obvious you observe in the code.
6. Do not edit or remove the `<!-- claude-wiki-meta` block at the bottom of the file — it is
   managed automatically.

{interaction_rules}
"""

_DEFAULT_UPDATE_PROMPT_EXISTING = """\
You are maintaining live documentation for a software project.
{instructions_block}
The following wiki documentation file may be out of date:
  {wiki_doc}

The following source files were recently changed:
{file_list}

Instructions:
1. Read the current source files listed above.
2. Read the current documentation at {wiki_doc}.
3. Determine whether the doc accurately reflects the current state of the changed code.
4. Update only sections that are wrong or missing. Preserve all existing structure.
5. A parent CLAUDE.md covers only: repo layout, tech stack, global conventions, interface
   overview (communication, shared types, DB), and review/pattern-discovery rules.
   Only update a parent if the change affects one of those concerns.
6. Do not add padding or filler. Only write what is genuinely useful for an LLM agent
   working in this codebase.
7. Document anything novel, proprietary, or non-obvious you observe in the changed code.
8. Do not edit or remove the `<!-- claude-wiki-meta` block at the bottom of the file — it is
   managed automatically.

{interaction_rules}
"""

_DEFAULT_MERGE_PROMPT = """\
You are resolving a documentation conflict for a claude-wiki managed project.

Two versions of the same CLAUDE.md file exist. Your job is to produce a single, authoritative
merged version that follows all template rules and preserves all valuable content.

---

## Wiki version (canonical managed copy)

Path: {wiki_doc}

Git history (wiki repo):
{wiki_git_log}

---

## Repo version (unmanaged edit made directly in the target repo)

Path: {repo_file}

Git history (target repo):
{repo_git_log}

---
{template_section}
## Merge instructions

**Step 1 — Assess intent and date context**
- Compare the git histories above. Determine whether:
  - One version is simply outdated (superseded by the other), OR
  - Both were edited independently on separate branches and both contain relevant information.
- Note whether the two versions cover overlapping concerns or complementary ones.
- State your assessment briefly as part of your rationale output (see Step 5).

**Step 2 — Evaluate template adherence**
- Compare each version against the required CLAUDE.md structure above.
- Note which version more closely follows the structural rules and content quality guidelines
  (no filler, no "what the code does" explanations, only non-obvious/proprietary information, etc.).
- The version with stronger template adherence is the **preferred base**.

**Step 3 — Merge**
- Use the preferred base as the structural foundation.
- Incorporate unique, non-redundant concepts from the other version that add genuine value.
- Do not duplicate content. Do not add padding. Only include what a future LLM agent
  working in this codebase would genuinely need.
- Resolve any contradictions in favor of the more recent or more specific information
  (use git dates to inform this).

**Step 4 — Write the result**
- Write the merged content to: {wiki_doc}
- Preserve the `<!-- claude-wiki-meta` block at the bottom exactly as-is.
- Do not touch {repo_file} — it will be replaced with a symlink automatically.

**Step 5 — Output rationale**
After writing, output a structured rationale in this exact format (this is captured in the merge log):

MERGE RATIONALE
  preferred-base: wiki|repo
  reason: <one sentence on why that base was chosen>
  intent-overlap: yes|no|partial
  outdated-version: wiki|repo|neither|both-current
  changes-from-other: <comma-separated list of concepts pulled from the non-base version, or "none">
  contradictions-resolved: <brief note, or "none">
{user_context}"""


def _ensure_prompt_template(path: Path, default: str, label: str):
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(default)
        print(f"  [created]  {label}  (edit to customize)")
    else:
        print(f"  [exists]   {label}  (skipped — already customized)")


def run_init(
    repo_path: str,
    no_detect_target_docs: bool = False,
    no_hooks: bool = False,
):
    from .hook_setup import run_hook_setup
    from .lib import load_new_entry_log

    repo = Path(repo_path).resolve()
    if not repo.exists():
        raise SystemExit(f"Repo path does not exist: {repo}")
    if not (repo / ".git").exists():
        raise SystemExit(f"Not a git repo: {repo}")

    config = {
        "repo_path": str(repo),
        "repo_name": repo.name,
        "skip_worktree": True,
    }
    save_config(config)
    print(f"Initialized wiki for {repo.name} at {repo}\n")

    _ensure_wiki_instructions()
    _ensure_llm_md()
    _ensure_instructions()
    _ensure_prompt_template(UPDATE_PROMPT_NEW_FILE, _DEFAULT_UPDATE_PROMPT_NEW,
                            "templates/update-prompt-new.md")
    _ensure_prompt_template(UPDATE_PROMPT_EXISTING_FILE, _DEFAULT_UPDATE_PROMPT_EXISTING,
                            "templates/update-prompt-existing.md")
    _ensure_prompt_template(MERGE_PROMPT_FILE, _DEFAULT_MERGE_PROMPT,
                            "templates/merge-prompt.md")
    _ensure_schema(repo)

    absorbed_count = 0
    absorbed_paths: list[str] = []
    if not no_detect_target_docs:
        from .check_paths import run_pull_docs
        absorbed_count, absorbed_paths = run_pull_docs(quiet=True)

    push_counts = run_push_docs(quiet=True)

    ensure_root_banner(quiet=True)

    if not no_hooks:
        run_hook_setup()

    new_entries = load_new_entry_log()
    manual = [e for e in new_entries if e.get("source") == "manual"]

    print("\nDone.")
    if absorbed_count:
        print(f"  absorbed:  {absorbed_count} existing doc(s) integrated")
    if push_counts.get("symlinks"):
        print(f"  symlinks:  {push_counts['symlinks']} created")
    if push_counts.get("new_docs"):
        print(f"  new docs:  {push_counts['new_docs']} placeholder(s)")

    if manual:
        print(f"\n  {len(manual)} placeholder doc(s) need content — run:")
        print(f"    claude-wiki update")
        for e in manual:
            print(f"    {e['rel_path']}")

    if absorbed_paths:
        print(f"\n  Absorbed docs (review recommended):")
        for p in absorbed_paths:
            print(f"    {p}")
