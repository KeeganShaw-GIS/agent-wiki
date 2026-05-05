"""eject: Replace symlinks in the target repo with real copies of the wiki docs.

Use this to detach one or all paths from the wiki. The wiki doc is preserved;
only the symlink in the target repo is replaced with a real file.

After ejecting, remove the path from schema.yaml if you no longer want the wiki
to manage it — or re-run push to restore the symlink.
"""

import shutil
import subprocess
from pathlib import Path

from .lib import (
    DOCS_ROOT, WIKI_ROOT, clear_conflict_log_for, clear_flag, doc_path,
    get_doc_filename, get_repo_path, load_conflict_log, load_schema, schema_paths,
    strip_wiki_header, symlink_path, walk_schema,
)


def _no_skip_worktree(repo: Path, rel_file: str):
    subprocess.run(
        ["git", "-C", str(repo), "update-index", "--no-skip-worktree", rel_file],
        capture_output=True,
    )


def run_eject(scope: str | None = None):
    repo = get_repo_path()
    schema = load_schema()
    nodes = walk_schema(schema)

    if scope is not None:
        nodes = [(rp, meta) for rp, meta in nodes if rp == scope]
        if not nodes:
            s_paths = schema_paths(schema)
            raise SystemExit(
                f"'{scope}' is not a managed doc path.\n"
                f"Managed paths: {', '.join(s_paths) or '(none)'}"
            )

    fn = get_doc_filename()
    symlinks_dir = repo / ".agent-wiki" / "symlinks"
    local_edits_dir = WIKI_ROOT / "logs" / "local-edits"
    ejected_paths = []

    for rel_path, _ in nodes:
        link = symlink_path(repo, rel_path)
        wiki_doc = doc_path(rel_path)
        display = f"docs/{rel_path}/{fn}" if rel_path else f"docs/{fn}"

        if not link.is_symlink():
            print(f"  [skip]     {link.relative_to(repo)}  (not a symlink)")
            continue

        if not wiki_doc.exists():
            print(f"  [skip]     {display}  (wiki doc missing)")
            continue

        # Back up wiki doc before replacing with stripped version
        if scope is not None:
            local_edits_dir.mkdir(parents=True, exist_ok=True)
            backup_name = (rel_path.replace("/", "-") or "root") + ".md"
            shutil.copy(wiki_doc, local_edits_dir / backup_name)

        content = strip_wiki_header(wiki_doc.read_text())
        link.unlink()
        link.write_text(content)
        _no_skip_worktree(repo, str(link.relative_to(repo)))

        # Remove the flat mirror symlink from .agent-wiki/symlinks/
        flat = ("root" if not rel_path else rel_path.replace("/", "-")) + Path(fn).suffix
        mirror = symlinks_dir / flat
        if mirror.is_symlink():
            mirror.unlink()

        ejected_paths.append(rel_path)
        print(f"  [ejected]  {link.relative_to(repo)}")

    # Always clear conflict log for all requested paths — eject resolves any conflict
    all_requested = [rp for rp, _ in nodes]
    clear_conflict_log_for(all_requested)
    if not load_conflict_log():
        clear_flag("multiple_versions")

    ejected = len(ejected_paths)
    if ejected:
        print(f"\n{ejected} file(s) ejected. Wiki docs in docs/ are untouched.")
        print("To stop managing these paths, remove them from schema.yaml.")
    else:
        print("Nothing ejected.")

    if scope is None:
        _backup_docs()
        _remove_wiki_integration(repo)


def _backup_docs():
    if not DOCS_ROOT.exists():
        return
    bak = WIKI_ROOT / "docs.bak"
    if bak.exists():
        shutil.rmtree(bak)
    shutil.copytree(DOCS_ROOT, bak)
    print(f"  [backup]   docs/ → docs.bak/")


def _remove_wiki_integration(repo: Path):
    # .agent-wiki/ folder
    cw_dir = repo / ".agent-wiki"
    if cw_dir.exists():
        shutil.rmtree(cw_dir)
        print(f"  [removed]  .agent-wiki/")

    # Git hooks owned by agent-wiki
    for hook_name in ("pre-commit", "post-checkout"):
        hook = repo / ".git" / "hooks" / hook_name
        if hook.exists() and "agent-wiki" in hook.read_text():
            bak = hook.with_suffix(".agent-wiki.bak")
            hook.rename(bak)
            print(f"  [backup]   .git/hooks/{hook_name} → {bak.name}")
