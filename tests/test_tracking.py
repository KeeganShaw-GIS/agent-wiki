"""Tests for tracking, untracking, and retracking schema paths."""

from utils import is_valid_symlink, run_wiki, write_schema

_BASE_SCHEMA = """\
root+:
  src+:
  frontend+:
    components+:
"""


class TestTrackNewPath:
    def test_add_path_to_schema_creates_doc(self, wiki_setup):
        wiki, repo = wiki_setup
        (repo / "api").mkdir(exist_ok=True)
        write_schema(wiki, _BASE_SCHEMA + "  api+:\n")
        run_wiki(wiki, ["push"])

        assert (wiki / "docs" / "api" / "CLAUDE.md").exists()

    def test_add_path_to_schema_creates_symlink(self, wiki_setup):
        wiki, repo = wiki_setup
        (repo / "api").mkdir(exist_ok=True)
        write_schema(wiki, _BASE_SCHEMA + "  api+:\n")
        run_wiki(wiki, ["push"])

        assert is_valid_symlink(repo / "api" / "CLAUDE.md")

    def test_track_path_with_existing_real_file(self, wiki_setup):
        """Tracking a path that already has a real CLAUDE.md absorbs it."""
        wiki, repo = wiki_setup
        (repo / "api").mkdir(exist_ok=True)
        (repo / "api" / "CLAUDE.md").write_text("# API\nReal content.\n")
        write_schema(wiki, _BASE_SCHEMA + "  api+:\n")
        run_wiki(wiki, ["push"])

        wiki_doc = wiki / "docs" / "api" / "CLAUDE.md"
        assert wiki_doc.exists()
        assert "Real content" in wiki_doc.read_text()
        assert is_valid_symlink(repo / "api" / "CLAUDE.md")


class TestUntrackPath:
    def test_untrack_removes_symlink(self, wiki_setup):
        wiki, repo = wiki_setup
        assert is_valid_symlink(repo / "src" / "CLAUDE.md")

        write_schema(wiki, "root+:\n  src~:\n  frontend+:\n    components+:\n")
        run_wiki(wiki, ["push"])

        src_doc = repo / "src" / "CLAUDE.md"
        assert src_doc.exists()
        assert not src_doc.is_symlink()

    def test_untrack_restores_real_file_from_wiki(self, wiki_setup):
        """Untracking a path moves the wiki doc content back to the target repo."""
        wiki, repo = wiki_setup
        wiki_doc = wiki / "docs" / "src" / "CLAUDE.md"
        assert wiki_doc.exists()

        write_schema(wiki, "root+:\n  src~:\n  frontend+:\n    components+:\n")
        run_wiki(wiki, ["push"])

        # A real file should exist in the target repo now
        real_file = repo / "src" / "CLAUDE.md"
        assert real_file.exists()
        assert not real_file.is_symlink()

    def test_untrack_strips_wiki_header(self, wiki_setup):
        """Untracked file must not contain any agent-wiki header or legacy banner."""
        wiki, repo = wiki_setup
        write_schema(wiki, "root+:\n  src~:\n  frontend+:\n    components+:\n")
        run_wiki(wiki, ["push"])

        content = (repo / "src" / "CLAUDE.md").read_text()
        assert "<!-- agent-wiki" not in content
        assert "WIKI MANAGED" not in content
        assert "agent-wiki-meta" not in content

    def test_untrack_removes_agent_wiki_mirror(self, wiki_setup):
        """The .agent-wiki/symlinks/src.md mirror symlink is removed on untrack."""
        wiki, repo = wiki_setup
        mirror = repo / ".agent-wiki" / "symlinks" / "src.md"
        assert mirror.exists() or mirror.is_symlink()

        write_schema(wiki, "root+:\n  src~:\n  frontend+:\n    components+:\n")
        run_wiki(wiki, ["push"])

        assert not mirror.exists()
        assert not mirror.is_symlink()

    def test_untrack_removes_nested_symlinks(self, wiki_setup):
        """Untracking a parent removes symlinks for all ~ children too."""
        wiki, repo = wiki_setup
        assert is_valid_symlink(repo / "frontend" / "components" / "CLAUDE.md")

        write_schema(wiki, "root+:\n  src+:\n  frontend~:\n    components~:\n")
        run_wiki(wiki, ["push"])

        assert not (repo / "frontend" / "CLAUDE.md").is_symlink()
        assert not (repo / "frontend" / "components" / "CLAUDE.md").is_symlink()

    def test_untrack_does_not_affect_other_paths(self, wiki_setup):
        wiki, repo = wiki_setup
        write_schema(wiki, "root+:\n  src~:\n  frontend+:\n    components+:\n")
        run_wiki(wiki, ["push"])

        # frontend and components should still be symlinks
        assert is_valid_symlink(repo / "frontend" / "CLAUDE.md")
        assert is_valid_symlink(repo / "frontend" / "components" / "CLAUDE.md")


class TestRetrackPath:
    def test_retrack_creates_symlink(self, wiki_setup):
        wiki, repo = wiki_setup

        # Untrack first
        write_schema(wiki, "root+:\n  src~:\n  frontend+:\n    components+:\n")
        run_wiki(wiki, ["push"])
        assert not (repo / "src" / "CLAUDE.md").is_symlink()

        # Retrack
        write_schema(wiki, _BASE_SCHEMA)
        run_wiki(wiki, ["push"])

        assert is_valid_symlink(repo / "src" / "CLAUDE.md")

    def test_retrack_absorbs_real_file_back(self, wiki_setup):
        """After retracking, any real file at the path is absorbed into the wiki."""
        wiki, repo = wiki_setup

        write_schema(wiki, "root+:\n  src~:\n  frontend+:\n    components+:\n")
        run_wiki(wiki, ["push"])

        # Retrack
        write_schema(wiki, _BASE_SCHEMA)
        run_wiki(wiki, ["push"])

        # The wiki doc should exist (absorbed from real file)
        assert (wiki / "docs" / "src" / "CLAUDE.md").exists()
        assert is_valid_symlink(repo / "src" / "CLAUDE.md")

    def test_retrack_preserves_content(self, wiki_setup):
        """Content in the real file is preserved after retracking."""
        wiki, repo = wiki_setup

        # Untrack and write custom content to the real file
        write_schema(wiki, "root+:\n  src~:\n  frontend+:\n    components+:\n")
        run_wiki(wiki, ["push"])
        real_file = repo / "src" / "CLAUDE.md"
        real_file.write_text("# Custom content added while untracked\n")

        # Retrack
        write_schema(wiki, _BASE_SCHEMA)
        run_wiki(wiki, ["push"])

        wiki_doc = wiki / "docs" / "src" / "CLAUDE.md"
        assert "Custom content" in wiki_doc.read_text()
