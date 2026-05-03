"""merge: LLM-assisted merge of conflicting wiki and repo CLAUDE.md versions."""

import os
import subprocess
from pathlib import Path

from .lib import (
    CONFLICT_LOG, MERGE_LOG, MERGE_PROMPT_FILE, SYNC_LOG, TEMPLATE_FILE, WIKI_ROOT,
    append_log, clear_conflict_log_for, clear_flag, get_repo_path,
    load_conflict_log, now_ts, resolve_claude_bin,
)
from .check_paths import make_symlink
from .validate import _apply_template


def _git_log_summary(file_path: Path, repo_root: Path, n: int = 5) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo_root), "log", "--follow", f"-{n}",
         "--format=%h %ad %an — %s", "--date=short", "--", str(file_path)],
        capture_output=True, text=True,
    )
    lines = result.stdout.strip()
    return lines if lines else "(no git history found for this file)"


def _build_merge_prompt(
    wiki_doc: Path,
    repo_file: Path,
    wiki_git_log: str,
    repo_git_log: str,
    user_prompt: str = "",
) -> str:
    if not MERGE_PROMPT_FILE.exists():
        raise SystemExit(
            f"Merge prompt template not found: {MERGE_PROMPT_FILE}\n"
            "Run `claude-wiki init --repo-path <path>` to generate it."
        )

    template_section = ""
    if TEMPLATE_FILE.exists():
        template_section = (
            "\n## Required CLAUDE.md structure (from templates/CLAUDE.template.md)\n\n"
            "Every CLAUDE.md must follow this template — both structurally and in terms of "
            "content rules:\n\n"
            f"```\n{TEMPLATE_FILE.read_text().strip()}\n```\n\n"
            "Use this as the structural and quality benchmark when evaluating both versions.\n"
        )

    user_context = (
        f"\n\n## Additional context from the user\n\n{user_prompt.strip()}"
        if user_prompt.strip() else ""
    )

    return _apply_template(MERGE_PROMPT_FILE.read_text(), {
        "wiki_doc": wiki_doc,
        "repo_file": repo_file,
        "wiki_git_log": wiki_git_log,
        "repo_git_log": repo_git_log,
        "template_section": template_section,
        "user_context": user_context,
    })


def run_merge(scope: str | None = None, prompt: str = "", no_prompt: bool = False):
    """Merge conflicting wiki and repo CLAUDE.md versions using an LLM."""
    conflicts = load_conflict_log()
    if not conflicts:
        print("No conflicts to merge. Run `claude-wiki pull` to detect conflicts.")
        return

    repo = get_repo_path()
    claude_bin = resolve_claude_bin()

    if scope is not None:
        normalized = scope.rstrip("/")
        conflicts = [c for c in conflicts if c.get("rel_path") in (scope, normalized)]
        if not conflicts:
            print(f"No conflict found for scope: {scope!r}")
            return

    print(f"Merging {len(conflicts)} conflict(s)...")

    resolved: list[str] = []

    for entry in conflicts:
        rel_path = entry["rel_path"]
        wiki_doc = Path(entry["wiki_doc"])
        repo_file = Path(entry["repo_file"])
        label = rel_path or "(root)"

        if not wiki_doc.exists():
            print(f"  SKIP {label} — wiki doc missing (run `claude-wiki push` first)")
            continue
        if not repo_file.exists() or repo_file.is_symlink():
            resolved.append(rel_path)
            continue

        wiki_git_log = _git_log_summary(wiki_doc, WIKI_ROOT)
        repo_git_log = _git_log_summary(repo_file, repo)

        print(f"  Merging: {label}")
        merge_prompt = _build_merge_prompt(wiki_doc, repo_file, wiki_git_log, repo_git_log, prompt)

        env = os.environ.copy()
        env.pop("CLAUDECODE", None)
        result = subprocess.run(
            [claude_bin, "-p", merge_prompt, "--allowedTools", "Read,Edit"],
            text=True,
            env=env,
        )

        status = "merged" if result.returncode == 0 else "failed"
        rationale_text = result.stdout.strip() if result.stdout else ""

        append_log(SYNC_LOG, {
            "ts": now_ts(),
            "status": status,
            "action": "merge",
            "rel_path": rel_path,
            "rationale": rationale_text[:500],
        })
        append_log(MERGE_LOG, {
            "ts": now_ts(),
            "status": status,
            "rel_path": rel_path,
            "wiki_git_log": wiki_git_log,
            "repo_git_log": repo_git_log,
            "rationale": rationale_text,
        })

        if result.returncode == 0:
            repo_file.unlink()
            make_symlink(repo_file, wiki_doc, quiet=False)
            resolved.append(rel_path)
            print(f"  [merged]   {label}")
        else:
            print(f"  WARNING: merge failed for {label}")

    if resolved:
        clear_conflict_log_for(resolved)
        if not load_conflict_log():
            clear_flag("multiple_versions")
            print("\n  All conflicts resolved. Flag cleared.")
        else:
            print(f"\n  Resolved {len(resolved)} conflict(s). {len(load_conflict_log())} remaining.")
