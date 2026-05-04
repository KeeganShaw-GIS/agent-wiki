"""status: Show pending drift statistics — docs that need attention."""

from pathlib import Path

from .lib import (
    ancestor_paths, best_schema_match, doc_path, get_doc_filename, get_repo_path,
    load_drift_log, load_new_entry_log, load_schema, resolve_scope, schema_paths,
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
        if f.is_file() and ".git" not in f.parts and f.name != get_doc_filename()
    ]


def run_status(scope=None):
    repo = get_repo_path()
    schema = load_schema()
    s_paths = schema_paths(schema)

    source_files, wiki_rel_paths = resolve_scope(scope, repo)

    new_entry_rel_paths: set[str] = set()
    if scope is None:
        for e in load_new_entry_log():
            rp = e.get("rel_path", "")
            if rp not in wiki_rel_paths:
                wiki_rel_paths.append(rp)
            new_entry_rel_paths.add(rp)

    if not wiki_rel_paths and not new_entry_rel_paths:
        print("Nothing pending — drift log and new-entry log are both empty.")
        return

    all_rel_paths = list(wiki_rel_paths)
    for rp in wiki_rel_paths:
        if rp in new_entry_rel_paths:
            continue
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
        if scope == "staged":
            scope_label = "git staged"
        elif scope == "diff":
            scope_label = "git diff"
        elif (repo / scope).is_dir():
            scope_label = f"folder  ({scope})"
        elif (repo / scope).is_file():
            scope_label = f"file  ({scope})"
        else:
            scope_label = f"git ref  ({scope})"

    print(f"Status — pending docs")
    print(f"  scope:  {scope_label}\n")
    for rel_path in all_rel_paths:
        dp = doc_path(rel_path)
        fn = get_doc_filename()
        display = f"docs/{rel_path}/{fn}" if rel_path else f"docs/{fn}"
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
        fn = get_doc_filename()
        existing_ancestors = [
            f"docs/{anc}/{fn}" if anc else f"docs/{fn}"
            for anc in ancestor_paths(rel_path, s_paths)
            if doc_path(anc).exists() and not _is_placeholder(doc_path(anc))
        ]
        if existing_ancestors:
            print(f"    context: {', '.join(existing_ancestors)}")
    print(f"\n{len(all_rel_paths)} doc(s) pending.")
