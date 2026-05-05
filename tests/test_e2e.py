"""End-to-end happy path tests for the full agent-wiki workflow."""

from utils import git_cmd, is_valid_symlink, read_flags, read_footer, read_log, run_wiki, write_schema


class TestHappyPath:
    def test_full_workflow(self, target_repo, wiki_dir):
        """
        Full e2e workflow:
          init → pull → untrack → add path → push → commit × 2
          (pre-commit captures drift on commit 2) → clear-flags resolves it.
        """
        repo = target_repo
        wiki = wiki_dir

        # 1. Init with hooks + base schema
        run_wiki(wiki, [
            "init", "--repo-path", str(repo),
            "--doc-filename", "CLAUDE.md",
            "--no-detect-target-docs",
        ])
        write_schema(wiki, "root+:\n  src+:\n  frontend+:\n    components+:\n")
        run_wiki(wiki, ["push"])

        assert is_valid_symlink(repo / "src" / "CLAUDE.md")
        assert is_valid_symlink(repo / "frontend" / "CLAUDE.md")

        # 2. Pull — absorb a doc that lives in the target repo but isn't in the schema yet
        (repo / "api").mkdir()
        (repo / "api" / "CLAUDE.md").write_text("# API routes\n")
        run_wiki(wiki, ["pull"])

        assert (wiki / "docs" / "api" / "CLAUDE.md").exists()
        footer = read_footer(wiki / "docs" / "api" / "CLAUDE.md")
        assert "Location" in footer  # absorbed doc gets metadata footer

        # 3. Untrack frontend (switch + → ~) and push
        write_schema(wiki, "root+:\n  src+:\n  frontend~:\n    components~:\n  api+:\n")
        run_wiki(wiki, ["push"])

        assert not (repo / "frontend" / "CLAUDE.md").is_symlink()
        assert not (repo / "frontend" / "components" / "CLAUDE.md").is_symlink()

        # 4. Add a new tracked path — push logs it as a new entry
        (repo / "services").mkdir()
        (repo / "services" / "auth.py").write_text("def login(): pass\n")
        write_schema(wiki, "root+:\n  src+:\n  frontend~:\n    components~:\n  api+:\n  services+:\n")
        run_wiki(wiki, ["push"])

        assert is_valid_symlink(repo / "services" / "CLAUDE.md")
        assert read_flags(wiki).get("new_entry") is True
        assert any(e["rel_path"] == "services" for e in read_log(wiki, "new-entry.jsonl"))

        # 5. Commit 1 — changes src/main.py; SourceCommitID stays at push-time HEAD
        #    Pre-commit fires but src hasn't drifted from SourceCommitID yet (this IS the drift)
        (repo / "src" / "main.py").write_text("def main(): return 1\n")
        git_cmd(repo, "add", "src/main.py")
        result = git_cmd(repo, "commit", "-m", "feat: first src change")
        assert result.returncode == 0  # hook is non-blocking

        # 6. Commit 2 — stages src again; pre-commit now sees src drifted since SourceCommitID
        (repo / "src" / "main.py").write_text("def main(): return 2\n")
        git_cmd(repo, "add", "src/main.py")
        result = git_cmd(repo, "commit", "-m", "feat: second src change")
        assert result.returncode == 0

        assert any(e["rel_path"] == "src" for e in read_log(wiki, "drift.jsonl"))
        assert read_flags(wiki).get("drift_detected") is True

        # 7. Change is trivial — clear flags without editing the doc
        original_commit = read_footer(wiki / "docs" / "src" / "CLAUDE.md").get("SourceCommitID")
        run_wiki(wiki, ["clear-flags", "--flag", "drift_detected"])

        assert not read_flags(wiki).get("drift_detected")
        new_commit = read_footer(wiki / "docs" / "src" / "CLAUDE.md").get("SourceCommitID")
        assert new_commit and new_commit != original_commit  # stamped to new HEAD


class TestBranchSwitchRestoresSymlinks:
    def test_post_checkout_restores_symlinks(self, wiki_hooked):
        """Switching branches restores any symlinks removed on a feature branch."""
        wiki, repo = wiki_hooked

        src_link = repo / "src" / "CLAUDE.md"
        assert is_valid_symlink(src_link)

        # Switch to a feature branch and delete a symlink there
        git_cmd(repo, "checkout", "-b", "feature")
        src_link.unlink()
        assert not src_link.exists()

        # Switch back — post-checkout hook fires and runs push
        result = git_cmd(repo, "checkout", "-")
        assert result.returncode == 0

        assert is_valid_symlink(src_link)
