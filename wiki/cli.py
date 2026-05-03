"""claude-wiki — documentation wiki manager for Claude Code CLAUDE.md files.

Commands:
  init              One-time setup for a target repo
  push              Sync schema <-> wiki docs <-> target symlinks
  pull              Absorb unmanaged CLAUDE.md files from the target repo
  detect-drift      Log changed files that need doc updates (pre-commit)
  update            LLM reads source files and updates docs by scope
"""

import argparse
import sys


def cmd_init(args):
    from .init import run_init
    run_init(
        repo_path=args.repo_path,
        no_detect_target_docs=args.no_detect_target_docs,
        no_hooks=args.no_hooks,
    )


def cmd_push_docs(args):
    from .check_paths import run_push_docs
    run_push_docs(detect_target_docs=args.detect_target_docs, verify=args.verify)


def cmd_detect_drift(args):
    from .detect_drift import run_detect_drift
    run_detect_drift(staged_only=args.staged)


def cmd_update_docs(args):
    from .validate import run_update_docs
    run_update_docs(scope=args.scope, no_prompt=args.no_prompt, dry_run=args.dry_run)


def cmd_eject(args):
    from .eject import run_eject
    run_eject(scope=args.scope)


def cmd_pull_docs(args):
    from .check_paths import run_pull_docs
    run_pull_docs(strategy=args.strategy)


def cmd_merge(args):
    from .merge import run_merge
    run_merge(scope=args.scope, prompt=args.prompt or "", no_prompt=args.no_prompt)


def cmd_hook_setup(args):
    from .hook_setup import run_hook_setup
    run_hook_setup(
        pre_commit=not args.no_pre_commit,
        post_checkout=not args.no_post_checkout,
        skip_worktree=not args.no_skip_worktree,
    )


def cmd_clear_flags(args):
    from .lib import (
        clear_flag, load_flags, load_conflict_log, load_drift_log,
        load_new_entry_log, FLAGS_FILE,
    )

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
        prog="claude-wiki",
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_init = sub.add_parser("init", help="One-time setup for a target repo")
    p_init.add_argument("--repo-path", required=True, metavar="PATH")
    p_init.add_argument("--no-detect-target-docs", action="store_true",
                        help="Skip absorbing unmanaged CLAUDE.md files from the target repo")
    p_init.add_argument("--no-hooks", action="store_true",
                        help="Skip installing git hooks and .claude-wiki/ in the target repo")

    p_pd = sub.add_parser("push", help="Sync schema <-> wiki <-> target symlinks")
    p_pd.add_argument("--detect-target-docs", action="store_true")
    p_pd.add_argument("--verify", action="store_true")

    p_dd = sub.add_parser("detect-drift", help="Log changed files (pre-commit hook)")
    p_dd.add_argument("--staged", action="store_true")

    p_v = sub.add_parser("update", help="LLM reads source files and updates docs by scope")
    p_v.add_argument("--scope", default=None, metavar="SCOPE")
    p_v.add_argument("--no-prompt", action="store_true")
    p_v.add_argument("--dry-run", action="store_true",
                     help="Show what would be updated without running the LLM")

    p_e = sub.add_parser("eject", help="Replace symlinks with real files, detaching from wiki")
    p_e.add_argument("--scope", default=None, metavar="PATH",
                     help="Schema rel-path to eject (e.g. frontend/walleter). Default: all.")

    p_pull = sub.add_parser("pull",
                            help="Scan target repo for unmanaged CLAUDE.md files and absorb them")
    p_pull.add_argument(
        "--strategy", choices=["skip", "wiki", "repo"], default="skip",
        help="Conflict resolution: skip (default, flag both), wiki (keep wiki), repo (keep repo)",
    )

    p_merge = sub.add_parser("merge",
                              help="LLM-assisted merge of conflicting wiki and repo CLAUDE.md versions")
    p_merge.add_argument("--scope", default=None, metavar="PATH",
                         help="Limit merge to a specific schema rel-path")
    p_merge.add_argument("--prompt", default=None, metavar="TEXT",
                         help="Optional context passed to the LLM to guide the merge")
    p_merge.add_argument("--no-prompt", action="store_true",
                         help="Non-interactive mode (no clarifying questions)")

    p_hs = sub.add_parser("hook-setup",
                          help="Install git hooks and wiki-path config in the target repo")
    p_hs.add_argument("--no-pre-commit", action="store_true",
                      help="Skip installing the pre-commit hook (detect-drift)")
    p_hs.add_argument("--no-post-checkout", action="store_true",
                      help="Skip installing the post-checkout hook (push --verify)")
    p_hs.add_argument("--no-skip-worktree", action="store_true",
                      help="Skip marking CLAUDE.md symlinks as skip-worktree")

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
                "  claude-wiki init --repo-path <path>\n\n"
                "Make sure you're running claude-wiki from your wiki root directory."
            )
            sys.exit(1)

    dispatch = {
        "init": cmd_init,
        "clear-flags": cmd_clear_flags,
        "push": cmd_push_docs,
        "detect-drift": cmd_detect_drift,
        "update": cmd_update_docs,
        "eject": cmd_eject,
        "pull": cmd_pull_docs,
        "merge": cmd_merge,
        "hook-setup": cmd_hook_setup,
    }
    dispatch[args.command](args)


if __name__ == "__main__":
    main()
