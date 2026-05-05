"""Tests for all wiki status flags."""

from utils import git_cmd, make_commit, read_flags, read_log, run_wiki, write_schema


def _commit_src_change(repo, content="def main(): return 42\n"):
    """Commit a change to src/main.py only, without staging untracked symlinks."""
    (repo / "src" / "main.py").write_text(content)
    git_cmd(repo, "add", "src/main.py")
    git_cmd(repo, "commit", "-m", "update src")


class TestNewEntryFlag:
    def test_push_new_path_sets_flag(self, wiki_setup):
        wiki, repo = wiki_setup
        (repo / "api").mkdir(exist_ok=True)
        write_schema(wiki, "root+:\n  src+:\n  frontend+:\n    components+:\n  api+:\n")
        run_wiki(wiki, ["push"])

        assert read_flags(wiki).get("new_entry") is True

    def test_new_entry_log_records_new_path(self, wiki_setup):
        wiki, repo = wiki_setup
        (repo / "api").mkdir(exist_ok=True)
        write_schema(wiki, "root+:\n  src+:\n  frontend+:\n    components+:\n  api+:\n")
        run_wiki(wiki, ["push"])

        entries = read_log(wiki, "new-entry.jsonl")
        assert any(e["rel_path"] == "api" for e in entries)


class TestDriftDetectedFlag:
    def test_detect_drift_sets_flag(self, wiki_setup):
        wiki, repo = wiki_setup
        _commit_src_change(repo)
        run_wiki(wiki, ["detect-drift"])

        assert read_flags(wiki).get("drift_detected") is True

    def test_detect_drift_logs_changed_files(self, wiki_setup):
        wiki, repo = wiki_setup
        _commit_src_change(repo)
        run_wiki(wiki, ["detect-drift"])

        entries = read_log(wiki, "drift.jsonl")
        src_entry = next((e for e in entries if e["rel_path"] == "src"), None)
        assert src_entry is not None
        assert "src/main.py" in src_entry["changed_files"]

    def test_detect_drift_idempotent(self, wiki_setup):
        """Running detect-drift twice doesn't duplicate log entries."""
        wiki, repo = wiki_setup
        _commit_src_change(repo)
        run_wiki(wiki, ["detect-drift"])
        run_wiki(wiki, ["detect-drift"])

        entries = read_log(wiki, "drift.jsonl")
        src_entries = [e for e in entries if e["rel_path"] == "src"]
        assert len(src_entries) == 1

    def test_detect_drift_clears_stale_entry(self, wiki_setup):
        """If a doc's changed files go away, its drift entry is removed."""
        wiki, repo = wiki_setup
        _commit_src_change(repo)
        run_wiki(wiki, ["detect-drift"])
        assert any(e["rel_path"] == "src" for e in read_log(wiki, "drift.jsonl"))

        # Stamp SourceCommitID at current HEAD so there's no drift
        run_wiki(wiki, ["clear-flags", "--flag", "drift_detected"])
        run_wiki(wiki, ["detect-drift"])

        entries = read_log(wiki, "drift.jsonl")
        assert not any(e["rel_path"] == "src" for e in entries)

    def test_detect_drift_staged_only(self, wiki_setup):
        """--staged limits drift to staged files (only staged paths are logged)."""
        wiki, repo = wiki_setup
        _commit_src_change(repo)  # src has drift vs SourceCommitID

        # Stage only a frontend file, not src
        (repo / "frontend" / "app.ts").write_text("export const x = 2;\n")
        git_cmd(repo, "add", "frontend/app.ts")

        run_wiki(wiki, ["detect-drift", "--staged"])

        entries = read_log(wiki, "drift.jsonl")
        rel_paths = [e["rel_path"] for e in entries]
        # src changed since SourceCommitID but wasn't staged — not logged with --staged
        assert "src" not in rel_paths


class TestMultipleVersionsFlag:
    def test_pull_repo_wins_by_default_and_sets_flag(self, wiki_setup):
        """Default pull absorbs repo version and sets multiple_versions as audit trail."""
        wiki, repo = wiki_setup
        (repo / "src" / "CLAUDE.md").unlink()
        (repo / "src" / "CLAUDE.md").write_text("# Edited in repo\n")

        run_wiki(wiki, ["pull"])

        assert read_flags(wiki).get("multiple_versions") is True
        # Repo content absorbed into wiki
        assert "Edited in repo" in (wiki / "docs" / "src" / "CLAUDE.md").read_text()
        # Old wiki version backed up
        assert (wiki / "logs" / "local-edits" / "src.md").exists()

    def test_pull_repo_wins_restores_symlink(self, wiki_setup):
        """After repo-wins pull, target path is a symlink again."""
        wiki, repo = wiki_setup
        (repo / "src" / "CLAUDE.md").unlink()
        (repo / "src" / "CLAUDE.md").write_text("# Edited in repo\n")

        run_wiki(wiki, ["pull"])

        from utils import is_valid_symlink
        assert is_valid_symlink(repo / "src" / "CLAUDE.md")

    def test_pull_skip_strategy_flags_without_absorbing(self, wiki_setup):
        """--strategy skip flags conflict but leaves both files untouched."""
        wiki, repo = wiki_setup
        original_wiki_content = (wiki / "docs" / "src" / "CLAUDE.md").read_text()
        (repo / "src" / "CLAUDE.md").unlink()
        (repo / "src" / "CLAUDE.md").write_text("# Conflict\n")

        run_wiki(wiki, ["pull", "--strategy", "skip"])

        assert read_flags(wiki).get("multiple_versions") is True
        assert (wiki / "docs" / "src" / "CLAUDE.md").read_text() == original_wiki_content

    def test_resolving_conflict_with_wiki_strategy_clears_flag(self, wiki_setup):
        wiki, repo = wiki_setup
        (repo / "src" / "CLAUDE.md").unlink()
        (repo / "src" / "CLAUDE.md").write_text("# Conflict\n")
        run_wiki(wiki, ["pull", "--strategy", "skip"])
        assert read_flags(wiki).get("multiple_versions") is True

        run_wiki(wiki, ["pull", "--strategy", "wiki"])

        assert not read_flags(wiki).get("multiple_versions")


class TestDocsOutOfSyncFlag:
    def test_push_verify_sets_flag_on_broken_symlink(self, wiki_setup):
        wiki, repo = wiki_setup
        (repo / "src" / "CLAUDE.md").unlink()
        run_wiki(wiki, ["push", "--verify"])

        flags = read_flags(wiki)
        assert "docs_out_of_sync" in flags

    def test_push_clears_docs_out_of_sync_flag(self, wiki_setup):
        wiki, repo = wiki_setup
        (repo / "src" / "CLAUDE.md").unlink()
        run_wiki(wiki, ["push", "--verify"])
        assert "docs_out_of_sync" in read_flags(wiki)

        run_wiki(wiki, ["push"])
        assert "docs_out_of_sync" not in read_flags(wiki)


class TestClearFlags:
    def test_clear_all_flags(self, wiki_setup):
        wiki, repo = wiki_setup
        (repo / "api").mkdir(exist_ok=True)
        write_schema(wiki, "root+:\n  src+:\n  frontend+:\n    components+:\n  api+:\n")
        run_wiki(wiki, ["push"])
        assert read_flags(wiki).get("new_entry") is True

        run_wiki(wiki, ["clear-flags"])

        assert "new_entry" not in read_flags(wiki)

    def test_clear_specific_flag(self, wiki_setup):
        wiki, repo = wiki_setup
        (repo / "api").mkdir(exist_ok=True)
        write_schema(wiki, "root+:\n  src+:\n  frontend+:\n    components+:\n  api+:\n")
        run_wiki(wiki, ["push"])

        run_wiki(wiki, ["clear-flags", "--flag", "new_entry"])

        assert "new_entry" not in read_flags(wiki)

    def test_clear_drift_stamps_source_commit_id(self, wiki_setup):
        wiki, repo = wiki_setup
        _commit_src_change(repo)
        run_wiki(wiki, ["detect-drift"])
        assert read_flags(wiki).get("drift_detected") is True

        run_wiki(wiki, ["clear-flags", "--flag", "drift_detected"])

        from utils import read_footer
        footer = read_footer(wiki / "docs" / "src" / "CLAUDE.md")
        assert footer.get("SourceCommitID")  # non-empty

    def test_clear_flags_auto_clears_resolved_flags(self, wiki_setup):
        """Flags backed by empty logs are auto-cleared even when not explicitly specified."""
        wiki, repo = wiki_setup
        (repo / "api").mkdir(exist_ok=True)
        write_schema(wiki, "root+:\n  src+:\n  frontend+:\n    components+:\n  api+:\n")
        run_wiki(wiki, ["push"])

        # Manually empty the new-entry log
        (wiki / "logs" / "new-entry.jsonl").write_text("")

        run_wiki(wiki, ["clear-flags"])

        # new_entry should be auto-cleared since the log is empty
        assert "new_entry" not in read_flags(wiki)
