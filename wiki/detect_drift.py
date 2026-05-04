"""detect-drift: Compute drift by comparing each doc's SourceCommitID to HEAD.

For each managed doc that has a SourceCommitID in its footer, runs
`git diff <SourceCommitID>..HEAD -- <path>` in the target repo to find changed
files. Logs one entry per doc that has drift. Idempotent — re-running overwrites
existing entries for the same doc rather than appending duplicates.

Called by the pre-commit hook (--staged computes against staged+HEAD). Safe to
call manually at any time.
"""

from .lib import (
    DRIFT_LOG,
    ancestor_paths, append_log, commit_is_ancestor, doc_path,
    get_doc_filename, git_head_hash, git_log_range, git_staged_files, load_drift_log,
    load_schema, now_ts, read_metadata_footer, schema_paths,
    get_repo_path, set_flag, walk_schema,
)


def run_detect_drift(staged_only: bool = False):
    repo = get_repo_path()
    schema = load_schema()
    s_paths = schema_paths(schema)
    head = git_head_hash(repo)
    if not head:
        return

    # Staged files — used to narrow drift to what's about to be committed
    staged = set(git_staged_files(repo)) if staged_only else None

    # Load existing log keyed by rel_path so we can overwrite stale entries
    existing = {e["rel_path"]: e for e in load_drift_log() if "rel_path" in e}

    logged = 0
    for rel_path, _ in walk_schema(schema):
        dp = doc_path(rel_path)
        if not dp.exists():
            continue

        footer = read_metadata_footer(dp)
        from_commit = footer.get("SourceCommitID")
        if not from_commit:
            continue
        if not commit_is_ancestor(repo, from_commit):
            continue

        scope_path = rel_path if rel_path else ""
        changed = git_log_range(repo, from_commit, scope_path)

        if staged is not None:
            changed = [f for f in changed if f in staged]

        if not changed:
            # No drift — remove stale entry if present
            if rel_path in existing:
                existing.pop(rel_path)
            continue

        parents = ancestor_paths(rel_path, s_paths)
        entry = {
            "ts": now_ts(),
            "trigger": "pre-commit" if staged_only else "manual",
            "rel_path": rel_path,
            "wiki_doc": f"docs/{rel_path}/{get_doc_filename()}" if rel_path else f"docs/{get_doc_filename()}",
            "from_commit": from_commit,
            "to_commit": head,
            "changed_files": changed,
            "parent_paths": parents,
        }
        existing[rel_path] = entry
        logged += 1

    # Rewrite the log with current state
    entries = list(existing.values())
    if entries:
        DRIFT_LOG.parent.mkdir(parents=True, exist_ok=True)
        DRIFT_LOG.write_text(
            "\n".join(__import__("json").dumps(e) for e in entries) + "\n"
        )
        set_flag("drift_detected")
        print(f"  [drift] {logged} doc(s) with drift logged to {DRIFT_LOG.relative_to(DRIFT_LOG.parent.parent)}")
    elif DRIFT_LOG.exists():
        DRIFT_LOG.write_text("")
