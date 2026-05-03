"""update: LLM reads source files and updates wiki docs based on scope.

Scope values:
  (none)          Use drift log entries
  path/to/file    Single source file
  path/to/dir     All files under directory
  diff            Staged + unstaged changes
  staged          Staged changes only
  <git-ref>       Files changed in that commit/branch
"""

import os
import subprocess
from pathlib import Path

from .lib import (
    INSTRUCTIONS_FILE, SYNC_LOG, UPDATE_PROMPT_EXISTING_FILE, UPDATE_PROMPT_NEW_FILE,
    ancestor_paths, append_log, best_schema_match,
    clear_drift_log_for, clear_flag, clear_new_entry_log,
    doc_path, get_repo_path, load_drift_log, load_new_entry_log,
    load_schema, now_ts, resolve_claude_bin, resolve_scope, schema_paths,
    write_metadata_footer,
)

_PLACEHOLDER = "Not yet populated"


def _is_placeholder(dp: Path) -> bool:
    return dp.exists() and _PLACEHOLDER in dp.read_text()


def _scan_dir_files(repo: Path, rel_path: str) -> list[str]:
    target = repo / rel_path if rel_path else repo
    if not target.is_dir():
        return []
    return [
        str(f.relative_to(repo))
        for f in sorted(target.rglob("*"))
        if f.is_file() and ".git" not in f.parts and f.name != "CLAUDE.md"
    ]


def _apply_template(template: str, variables: dict) -> str:
    """Substitute {key} placeholders; unmapped keys are left as-is."""
    result = template
    for key, value in variables.items():
        result = result.replace(f"{{{key}}}", str(value))
    return result


def _load_instructions() -> str:
    if INSTRUCTIONS_FILE.exists():
        return f"\n## House Rules (from templates/instructions.md)\n\n{INSTRUCTIONS_FILE.read_text().strip()}\n"
    return ""


_INTERACTION_RULES_NOPROMPT = (
    "Do not ask questions. Make best-effort updates with the available context. "
    "Note any ambiguities or missing context in your response."
)

_INTERACTION_RULES_INTERACTIVE = (
    "You are in interactive mode. Follow these rules:\n"
    "- If task context is unclear, ask the user to share a ticket or describe the change.\n"
    "- If a new CLAUDE.md at a deeper path would improve agent guidance, propose it with "
    "a one-line reason and ask for confirmation. On approval: edit schema.yaml to add the "
    "path (+ suffix on the new key), then create the doc file at "
    "docs/<path>/CLAUDE.md and populate it. Do not run any scripts — check-paths runs "
    "automatically after you finish to create the symlink.\n"
    "- If source files outside the current scope would improve accuracy, name them and ask "
    "if the user wants to expand scope.\n"
    "- If something in the doc looks inconsistent but wasn't touched by this scope, flag it "
    "and ask: 'I noticed X looks inconsistent — want me to include that fix?'\n"
    "- Do not change sections unrelated to the scoped files without confirmation."
)


def build_prompt(wiki_doc: Path, source_files: list[str], repo: Path, no_prompt: bool,
                 is_new: bool = False,
                 ancestor_docs: list[tuple[str, str]] | None = None) -> str:
    file_list = "\n".join(f"  {repo / f}" for f in source_files)
    interaction_rules = _INTERACTION_RULES_NOPROMPT if no_prompt else _INTERACTION_RULES_INTERACTIVE

    if is_new:
        ancestor_block = ""
        if ancestor_docs:
            sections = "\n\n".join(
                f"### {label}\n\n{content.strip()}"
                for label, content in ancestor_docs
            )
            ancestor_block = (
                f"\nAncestor documentation (read-only context — do not edit these files):\n\n"
                f"{sections}\n"
            )
        template_file = UPDATE_PROMPT_NEW_FILE
    else:
        ancestor_block = ""
        template_file = UPDATE_PROMPT_EXISTING_FILE

    if template_file.exists():
        template = template_file.read_text()
    else:
        # Fallback: prompt the user to run init to generate the template
        raise SystemExit(
            f"Prompt template not found: {template_file}\n"
            "Run `claude-wiki init --repo-path <path>` to generate it."
        )

    return _apply_template(template, {
        "wiki_doc": wiki_doc,
        "file_list": file_list,
        "ancestor_block": ancestor_block,
        "interaction_rules": interaction_rules,
        "instructions_block": _load_instructions(),
    })


def _explicit_scope_type(scope: str, repo: Path) -> str:
    if scope == "staged":
        return "git staged"
    if scope == "diff":
        return "git diff"
    if (repo / scope).is_dir():
        return f"folder  ({scope})"
    if (repo / scope).is_file():
        return f"file  ({scope})"
    return f"git ref  ({scope})"


def run_update_docs(scope=None, no_prompt: bool = False, dry_run: bool = False):
    claude_bin = resolve_claude_bin()
    repo = get_repo_path()
    schema = load_schema()
    s_paths = schema_paths(schema)

    source_files, wiki_rel_paths = resolve_scope(scope, repo)

    # When running without an explicit scope, also pull in new-entry paths.
    new_entry_rel_paths: set[str] = set()
    if scope is None:
        for e in load_new_entry_log():
            rp = e.get("rel_path", "")
            if rp not in wiki_rel_paths:
                wiki_rel_paths.append(rp)
            new_entry_rel_paths.add(rp)

    if not wiki_rel_paths:
        print("Nothing to update — no wiki docs map to the current scope.")
        return

    all_rel_paths = list(wiki_rel_paths)
    for rp in wiki_rel_paths:
        if rp in new_entry_rel_paths:
            continue  # new docs: generate only this path, don't cascade to ancestors
        for anc in ancestor_paths(rp, s_paths):
            if anc not in all_rel_paths:
                all_rel_paths.append(anc)

    def files_for_doc(rel_path: str) -> list[str]:
        return [f for f in source_files if best_schema_match(f, [rel_path]) is not None]

    has_drift = bool(source_files) and scope is None and bool(set(wiki_rel_paths) - new_entry_rel_paths)
    if scope is None:
        if new_entry_rel_paths and has_drift:
            scope_label = "drift + new-entries"
        elif new_entry_rel_paths:
            scope_label = "new-entries"
        else:
            scope_label = "drift-log"
    else:
        scope_label = _explicit_scope_type(scope, repo)

    if dry_run:
        print(f"Dry run — update plan")
        print(f"  scope:  {scope_label}\n")
        for rel_path in all_rel_paths:
            dp = doc_path(rel_path)
            display = f"docs/{rel_path}/CLAUDE.md" if rel_path else "docs/CLAUDE.md"
            if rel_path in new_entry_rel_paths:
                kind = "new-file"
            elif scope is None:
                kind = "drift"
            else:
                kind = "manual"
            is_new = _is_placeholder(dp)
            scoped = files_for_doc(rel_path)
            if not scoped and (is_new or rel_path in new_entry_rel_paths):
                scoped = _scan_dir_files(repo, rel_path)
            print(f"  {display:<50}  [{kind}]  {len(scoped)} source file(s)")
            existing_ancestors = [
                f"docs/{anc}/CLAUDE.md" if anc else "docs/CLAUDE.md"
                for anc in ancestor_paths(rel_path, s_paths)
                if doc_path(anc).exists() and not _is_placeholder(doc_path(anc))
            ]
            if existing_ancestors:
                print(f"    context: {', '.join(existing_ancestors)}")
        print(f"\n{len(all_rel_paths)} doc(s) would be updated.")
        return

    print(f"Updating {len(all_rel_paths)} doc(s)...")
    append_log(SYNC_LOG, {
        "ts": now_ts(),
        "status": "started",
        "scope": scope_label,
        "docs": [f"docs/{r}/CLAUDE.md" if r else "docs/CLAUDE.md" for r in all_rel_paths],
    })

    validated_new_entries: list[str] = []
    validated_rel_paths: list[str] = []

    for rel_path in all_rel_paths:
        dp = doc_path(rel_path)
        display = f"docs/{rel_path}/CLAUDE.md" if rel_path else "docs/CLAUDE.md"

        if not dp.exists():
            print(f"  SKIP {display} (not found — run check-paths first)")
            continue

        is_new = _is_placeholder(dp)
        needs_dir_scan = is_new or rel_path in new_entry_rel_paths

        scoped = files_for_doc(rel_path)
        if not scoped:
            if needs_dir_scan:
                scoped = _scan_dir_files(repo, rel_path)
            else:
                scoped = source_files

        if not scoped:
            print(f"  SKIP {display} (no source files found)")
            continue

        ancestor_docs = None
        if is_new:
            ancestors = [
                (f"docs/{anc}/CLAUDE.md" if anc else "docs/CLAUDE.md", doc_path(anc))
                for anc in ancestor_paths(rel_path, s_paths)
            ]
            ancestor_docs = [
                (label, adp.read_text())
                for label, adp in ancestors
                if adp.exists() and not _is_placeholder(adp)
            ]

        print(f"  {'Generating' if is_new else 'Updating'}: {display}")
        prompt = build_prompt(dp, scoped, repo, no_prompt, is_new=is_new, ancestor_docs=ancestor_docs)

        # Interactive mode allows Write so Claude can propose and create new CLAUDE.md files.
        # Non-interactive (automated) mode restricts to Read+Edit — existing docs only.
        allowed_tools = "Read,Edit,Write" if not no_prompt else "Read,Edit"

        env = os.environ.copy()
        env.pop("CLAUDECODE", None)
        result = subprocess.run(
            [claude_bin, "-p", prompt, "--allowedTools", allowed_tools],
            text=True,
            env=env,
        )

        status = "finished" if result.returncode == 0 else "failed"
        append_log(SYNC_LOG, {
            "ts": now_ts(),
            "status": status,
            "doc": display,
            "rationale": result.stdout.strip()[:500] if result.stdout else "",
        })

        if result.returncode == 0:
            write_metadata_footer(dp, rel_path, "claude-wiki update")
            validated_rel_paths.append(rel_path)
            if rel_path in new_entry_rel_paths:
                validated_new_entries.append(rel_path)
        else:
            print(f"  WARNING: claude invocation failed for {display}")

    if validated_new_entries:
        clear_new_entry_log(validated_new_entries)
        if not load_new_entry_log():
            clear_flag("new_entry")

    if scope is None and validated_rel_paths:
        clear_drift_log_for(validated_rel_paths)
        if not load_drift_log():
            clear_flag("drift_detected")
        clear_flag("docs_out_of_sync")

    print("\nUpdate complete.")
