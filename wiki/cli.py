"""agent-wiki — documentation wiki manager for LLM agents.

Commands:
  init              One-time setup for a target repo
  push              Sync schema <-> wiki docs <-> target symlinks
  pull              Absorb unmanaged doc files from the target repo
  detect-drift      Log changed files that need doc updates (pre-commit)
  status            Show pending drift statistics
"""

import argparse
import sys


def cmd_init(args):
    from .init import run_init
    run_init(
        repo_path=args.repo_path,
        no_detect_target_docs=args.no_detect_target_docs,
        no_hooks=args.no_hooks,
        doc_filename=args.doc_filename,
    )


def cmd_push_docs(args):
    from .check_paths import run_push_docs
    run_push_docs(detect_target_docs=args.detect_target_docs, verify=args.verify)


def cmd_detect_drift(args):
    from .detect_drift import run_detect_drift
    run_detect_drift(staged_only=args.staged)


def cmd_eject(args):
    from .eject import run_eject
    run_eject(scope=args.scope)


def cmd_pull_docs(args):
    from .check_paths import run_pull_docs
    run_pull_docs(strategy=args.strategy)


def cmd_status(args):
    from .status import run_status
    run_status(scope=args.scope)


def cmd_hook_setup(args):
    from .hook_setup import run_hook_setup
    run_hook_setup(
        pre_commit=not args.no_pre_commit,
        post_checkout=not args.no_post_checkout,
        skip_worktree=not args.no_skip_worktree,
    )


def _stamp_drift_checked():
    """Stamp SourceCommitID=HEAD on every doc currently in the drift log."""
    from .lib import (
        doc_path, get_repo_path, git_head_hash, load_drift_log,
        write_metadata_footer,
    )
    repo = get_repo_path()
    head = git_head_hash(repo)
    if not head:
        return
    for entry in load_drift_log():
        rel_path = entry.get("rel_path", "")
        dp = doc_path(rel_path)
        if dp.exists():
            write_metadata_footer(dp, rel_path, "agent-wiki clear-flags",
                                  source_commit=head)
            print(f"  [stamped]  {entry.get('wiki_doc', rel_path)}  SourceCommitID={head}")


def cmd_add_agent(args):
    from pathlib import Path
    from .lib import get_repo_path
    repo = get_repo_path()
    agents_dir = repo / ".agent-wiki" / "agents"
    agents_dir.mkdir(parents=True, exist_ok=True)
    name = args.name if args.name.endswith(".md") else args.name + ".md"
    target = agents_dir / name
    if target.exists():
        print(f"  [exists]  .agent-wiki/agents/{name}")
        return
    target.write_text("")
    print(f"  [created]  .agent-wiki/agents/{name}")


def cmd_clear_flags(args):
    from .lib import (
        clear_flag, load_flags, load_conflict_log, load_drift_log,
        load_new_entry_log, FLAGS_FILE,
    )

    # When explicitly clearing drift_detected, stamp SourceCommitID on each drifted doc
    flags_to_clear = set(args.flag or [])
    clearing_drift = (
        "drift_detected" in flags_to_clear
        or (not args.flag)  # clearing all flags
    )
    if clearing_drift and load_drift_log():
        _stamp_drift_checked()

    # Auto-resolve flags whose backing log is now empty
    _auto_clear = {
        "multiple_versions": lambda: not load_conflict_log(),
        "drift_detected":    lambda: not load_drift_log(),
        "new_entry":         lambda: not load_new_entry_log(),
    }
    auto_cleared = []
    for key, is_resolved in _auto_clear.items():
        if key in load_flags() and is_resolved():
            clear_flag(key)
            auto_cleared.append(key)
    if auto_cleared:
        for k in auto_cleared:
            print(f"  [auto-cleared]  {k}  (backing log is empty)")

    flags = load_flags()
    if not flags:
        print("No flags set.")
        return

    if args.flag:
        clear_flag(*args.flag)
        for f in args.flag:
            print(f"  [cleared]  {f}")
    else:
        keys = [k for k in flags if k != "last_updated"]
        clear_flag(*keys)
        for k in keys:
            print(f"  [cleared]  {k}")
    print(f"  flags.json updated: {FLAGS_FILE}")


def main():
    parser = argparse.ArgumentParser(
        prog="agent-wiki",
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_init = sub.add_parser("init", help="One-time setup for a target repo")
    p_init.add_argument("--repo-path", required=True, metavar="PATH")
    p_init.add_argument("--doc-filename", default=None, metavar="FILENAME",
                        help="Doc filename to manage (e.g. CLAUDE.md, AGENTS.md). Prompted if omitted.")
    p_init.add_argument("--no-detect-target-docs", action="store_true",
                        help="Skip absorbing unmanaged doc files from the target repo")
    p_init.add_argument("--no-hooks", action="store_true",
                        help="Skip installing git hooks and .agent-wiki/ in the target repo")

    p_pd = sub.add_parser("push", help="Sync schema <-> wiki <-> target symlinks")
    p_pd.add_argument("--detect-target-docs", action="store_true")
    p_pd.add_argument("--verify", action="store_true")

    p_dd = sub.add_parser("detect-drift", help="Log changed files (pre-commit hook)")
    p_dd.add_argument("--staged", action="store_true")

    p_e = sub.add_parser("eject", help="Replace symlinks with real files, detaching from wiki")
    p_e.add_argument("--scope", default=None, metavar="PATH",
                     help="Schema rel-path to eject (e.g. frontend/walleter). Default: all.")

    p_pull = sub.add_parser("pull",
                            help="Scan target repo for unmanaged doc files and absorb them")
    p_pull.add_argument(
        "--strategy", choices=["skip", "wiki", "repo"], default="repo",
        help="Conflict resolution: repo (default, repo wins + backup wiki), wiki (keep wiki), skip (flag both)",
    )

    p_hs = sub.add_parser("hook-setup",
                          help="Install git hooks and wiki-path config in the target repo")
    p_hs.add_argument("--no-pre-commit", action="store_true",
                      help="Skip installing the pre-commit hook (detect-drift)")
    p_hs.add_argument("--no-post-checkout", action="store_true",
                      help="Skip installing the post-checkout hook (push --verify)")
    p_hs.add_argument("--no-skip-worktree", action="store_true",
                      help="Skip marking doc symlinks as skip-worktree")

    p_st = sub.add_parser("status", help="Show pending drift statistics")
    p_st.add_argument("--scope", default=None, metavar="SCOPE",
                      help="Scope: path, diff, staged, or git ref. Default: drift + new-entry logs.")

    p_aa = sub.add_parser("add-agent", help="Create a blank doc in .agent-wiki/agents/")
    p_aa.add_argument("--name", required=True, metavar="NAME",
                      help="Agent doc filename (e.g. researcher or researcher.md)")

    p_cf = sub.add_parser("clear-flags", help="Manually clear one or all wiki status flags")
    p_cf.add_argument("--flag", action="append", metavar="FLAG",
                      help="Flag to clear (repeatable). Omit to clear all. "
                           "Known flags: new_entry, drift_detected, docs_out_of_sync")

    args = parser.parse_args()

    if args.command != "init":
        from pathlib import Path
        if not (Path.cwd() / "config.json").exists():
            print(
                "Error: no config.json found in current directory.\n"
                "Run init first:\n"
                "  agent-wiki init --repo-path <path>\n\n"
                "Make sure you're running agent-wiki from your wiki root directory."
            )
            sys.exit(1)

    dispatch = {
        "init": cmd_init,
        "clear-flags": cmd_clear_flags,
        "push": cmd_push_docs,
        "detect-drift": cmd_detect_drift,
        "eject": cmd_eject,
        "pull": cmd_pull_docs,
        "hook-setup": cmd_hook_setup,
        "status": cmd_status,
        "add-agent": cmd_add_agent,
    }
    dispatch[args.command](args)


if __name__ == "__main__":
    main()
