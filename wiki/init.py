"""init: One-time setup — record target repo path, create docs and symlinks, install hooks."""

from importlib.resources import files
from pathlib import Path

from .lib import (
    CONFIG_FILE, INSTRUCTIONS_FILE, SCHEMA_FILE, WIKI_ROOT,
    WIKI_MERGE_FILE, WIKI_UPDATE_FILE,
    save_config, save_schema,
)

LLM_MD_FILE = WIKI_ROOT / "llm.md"

_TEMPLATES = files("wiki").joinpath("templates")


def _pkg(name: str) -> str:
    return _TEMPLATES.joinpath(name).read_text(encoding="utf-8")


_LLM_MD = _pkg("llm.md")
_DEFAULT_INSTRUCTIONS = _pkg("instructions.md")
_WIKI_INSTRUCTIONS = _pkg("wiki-instructions.md")

_WIKI_INSTRUCTIONS_FILE = WIKI_ROOT / "wiki-instructions.md"


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


def _ensure_instruction_file(path: Path, default: str, label: str):
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(default)
        print(f"  [created]  {label}  (edit to customize)")
    else:
        print(f"  [exists]   {label}  (skipped — already customized)")


def _ensure_schema(_repo=None):
    if not SCHEMA_FILE.exists():
        save_schema({"root+": {}})
        print("  [created]  schema.yaml")
    else:
        print("  [exists]   schema.yaml  (skipped)")


def _prompt_doc_filename() -> str:
    print("\nWhich doc filename does your LLM agent use?")
    print("  1) CLAUDE.md  — Anthropic Claude Code")
    print("  2) AGENTS.md  — OpenAI Codex agents")
    print("  3) Custom")
    choice = input("Choice [1]: ").strip() or "1"
    if choice == "1":
        return "CLAUDE.md"
    if choice == "2":
        return "AGENTS.md"
    if choice == "3":
        name = input("Filename (e.g. GEMINI.md): ").strip()
        if not name:
            return "CLAUDE.md"
        return name
    return "CLAUDE.md"


def run_init(
    repo_path: str,
    no_detect_target_docs: bool = False,
    no_hooks: bool = False,
    doc_filename: str | None = None,
):
    from .hook_setup import run_hook_setup
    from .lib import load_new_entry_log

    repo = Path(repo_path).resolve()
    if not repo.exists():
        raise SystemExit(f"Repo path does not exist: {repo}")
    if not (repo / ".git").exists():
        raise SystemExit(f"Not a git repo: {repo}")

    if doc_filename is None:
        doc_filename = _prompt_doc_filename()

    config = {
        "repo_path": str(repo),
        "repo_name": repo.name,
        "skip_worktree": True,
        "doc_filename": doc_filename,
    }
    save_config(config)
    print(f"\nInitialized wiki for {repo.name} at {repo}  (doc: {doc_filename})\n")

    _ensure_wiki_instructions()
    _ensure_llm_md()
    _ensure_instructions()
    _ensure_instruction_file(WIKI_UPDATE_FILE, _pkg("WIKI_UPDATE.md"),
                             "templates/WIKI_UPDATE.md")
    _ensure_instruction_file(WIKI_MERGE_FILE, _pkg("WIKI_MERGE.md"),
                             "templates/WIKI_MERGE.md")
    _ensure_schema(repo)

    from .check_paths import ensure_root_banner, run_push_docs

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
        print(f"\n  {len(manual)} placeholder doc(s) need content:")
        for e in manual:
            print(f"    {e['rel_path']}")

    if absorbed_paths:
        print(f"\n  Absorbed docs (review recommended):")
        for p in absorbed_paths:
            print(f"    {p}")
