"""Tests for metadata footer: timestamps, touched-by, and SourceCommitID."""

from datetime import date

from utils import git_cmd, make_commit, read_flags, read_footer, run_wiki


class TestMetadataFooterCreation:
    def test_new_doc_has_footer(self, wiki_setup):
        wiki, repo = wiki_setup
        footer = read_footer(wiki / "docs" / "src" / "CLAUDE.md")
        assert footer, "Expected metadata footer to be present"

    def test_footer_has_location_field(self, wiki_setup):
        wiki, repo = wiki_setup
        footer = read_footer(wiki / "docs" / "src" / "CLAUDE.md")
        assert "Location" in footer
        assert "src/CLAUDE.md" in footer["Location"]

    def test_footer_has_last_touched_by(self, wiki_setup):
        wiki, repo = wiki_setup
        footer = read_footer(wiki / "docs" / "src" / "CLAUDE.md")
        assert "LastTouchedBy" in footer
        assert "agent-wiki" in footer["LastTouchedBy"]

    def test_footer_has_change_date(self, wiki_setup):
        wiki, repo = wiki_setup
        footer = read_footer(wiki / "docs" / "src" / "CLAUDE.md")
        assert footer.get("ChangeDate") == date.today().isoformat()

    def test_footer_has_source_commit_id(self, wiki_setup):
        """push sets SourceCommitID to current HEAD when creating the doc."""
        wiki, repo = wiki_setup
        footer = read_footer(wiki / "docs" / "src" / "CLAUDE.md")
        assert footer.get("SourceCommitID")

    def test_root_doc_has_footer(self, wiki_setup):
        wiki, repo = wiki_setup
        footer = read_footer(wiki / "docs" / "CLAUDE.md")
        assert footer
        assert "Location" in footer

    def test_nested_doc_location_correct(self, wiki_setup):
        wiki, repo = wiki_setup
        footer = read_footer(wiki / "docs" / "frontend" / "components" / "CLAUDE.md")
        assert "frontend/components/CLAUDE.md" in footer.get("Location", "")


class TestSourceCommitIdLifecycle:
    def test_source_commit_id_updated_after_clear_flags(self, wiki_setup):
        """clear-flags --flag drift_detected stamps SourceCommitID with current HEAD."""
        wiki, repo = wiki_setup
        original_commit = read_footer(wiki / "docs" / "src" / "CLAUDE.md").get("SourceCommitID")

        # Stage and commit ONLY src/main.py to avoid staging untracked symlinks
        (repo / "src" / "main.py").write_text("def main(): return 99\n")
        git_cmd(repo, "add", "src/main.py")
        git_cmd(repo, "commit", "-m", "update src")
        run_wiki(wiki, ["detect-drift"])
        assert read_flags(wiki).get("drift_detected") is True

        run_wiki(wiki, ["clear-flags", "--flag", "drift_detected"])

        new_commit = read_footer(wiki / "docs" / "src" / "CLAUDE.md").get("SourceCommitID")
        assert new_commit
        assert new_commit != original_commit

    def test_undrifted_doc_source_commit_unchanged(self, wiki_setup):
        """A doc with no drift keeps its SourceCommitID after clear-flags."""
        wiki, repo = wiki_setup
        original = read_footer(wiki / "docs" / "frontend" / "CLAUDE.md").get("SourceCommitID")

        # Stage and commit ONLY src/main.py to avoid accidentally staging symlinks
        (repo / "src" / "main.py").write_text("def main(): return 99\n")
        git_cmd(repo, "add", "src/main.py")
        git_cmd(repo, "commit", "-m", "update src only")
        run_wiki(wiki, ["detect-drift"])
        run_wiki(wiki, ["clear-flags", "--flag", "drift_detected"])

        new = read_footer(wiki / "docs" / "frontend" / "CLAUDE.md").get("SourceCommitID")
        assert new == original


class TestFooterOnPull:
    def test_pulled_doc_gets_footer(self, wiki_setup):
        wiki, repo = wiki_setup
        (repo / "api").mkdir(exist_ok=True)
        (repo / "api" / "CLAUDE.md").write_text("# API\n")
        run_wiki(wiki, ["pull"])

        footer = read_footer(wiki / "docs" / "api" / "CLAUDE.md")
        assert footer
        assert "Location" in footer

    def test_pulled_doc_footer_has_correct_location(self, wiki_setup):
        wiki, repo = wiki_setup
        (repo / "api").mkdir(exist_ok=True)
        (repo / "api" / "CLAUDE.md").write_text("# API\n")
        run_wiki(wiki, ["pull"])

        footer = read_footer(wiki / "docs" / "api" / "CLAUDE.md")
        assert "api/CLAUDE.md" in footer.get("Location", "")
