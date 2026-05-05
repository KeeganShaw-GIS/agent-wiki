"""Tests for agent-wiki pull command."""

from utils import is_valid_symlink, read_flags, read_footer, read_log, run_wiki


class TestPullAbsorb:
    def test_absorbs_unmanaged_doc(self, wiki_setup):
        wiki, repo = wiki_setup
        unmanaged = repo / "api" / "CLAUDE.md"
        unmanaged.parent.mkdir(exist_ok=True)
        unmanaged.write_text("# API\nContent.\n")

        run_wiki(wiki, ["pull"])

        assert is_valid_symlink(unmanaged)
        wiki_doc = wiki / "docs" / "api" / "CLAUDE.md"
        assert wiki_doc.exists()
        assert "API" in wiki_doc.read_text()

    def test_absorbed_doc_updates_schema(self, wiki_setup):
        wiki, repo = wiki_setup
        (repo / "api").mkdir(exist_ok=True)
        (repo / "api" / "CLAUDE.md").write_text("# API\n")

        run_wiki(wiki, ["pull"])

        assert "api+" in (wiki / "schema.yaml").read_text()

    def test_absorbed_doc_gets_metadata_footer(self, wiki_setup):
        wiki, repo = wiki_setup
        (repo / "api").mkdir(exist_ok=True)
        (repo / "api" / "CLAUDE.md").write_text("# API\n")

        run_wiki(wiki, ["pull"])

        footer = read_footer(wiki / "docs" / "api" / "CLAUDE.md")
        assert "Location" in footer
        assert "LastTouchedBy" in footer

    def test_absorbed_doc_adds_path_to_schema(self, wiki_setup):
        """Absorbed docs are added to schema.yaml (not new-entry.jsonl — they already have content)."""
        wiki, repo = wiki_setup
        (repo / "api").mkdir(exist_ok=True)
        (repo / "api" / "CLAUDE.md").write_text("# API\n")

        run_wiki(wiki, ["pull"])

        assert "api+" in (wiki / "schema.yaml").read_text()

    def test_no_unmanaged_docs_prints_nothing_found(self, wiki_setup):
        wiki, repo = wiki_setup
        result = run_wiki(wiki, ["pull"])
        assert "No unmanaged" in result.stdout

    def test_root_doc_absorbed_gets_wiki_banner(self, wiki_setup):
        """A root CLAUDE.md absorbed by pull gets the WIKI MANAGED banner."""
        wiki, repo = wiki_setup
        # Remove the existing root symlink and place a real file
        (repo / "CLAUDE.md").unlink()
        (repo / "CLAUDE.md").write_text("# Project Root\nContent.\n")

        run_wiki(wiki, ["pull", "--strategy", "repo"])

        content = (wiki / "docs" / "CLAUDE.md").read_text()
        assert "WIKI MANAGED" in content


class TestPullConflicts:
    def test_conflict_skip_strategy_sets_flag(self, wiki_setup):
        wiki, repo = wiki_setup
        # Create a real file where there's already a managed symlink
        (repo / "src" / "CLAUDE.md").unlink()
        (repo / "src" / "CLAUDE.md").write_text("# Conflicting src\n")

        run_wiki(wiki, ["pull"])  # default: skip

        assert read_flags(wiki).get("multiple_versions") is True

    def test_conflict_skip_strategy_logs_conflict(self, wiki_setup):
        wiki, repo = wiki_setup
        (repo / "src" / "CLAUDE.md").unlink()
        (repo / "src" / "CLAUDE.md").write_text("# Conflict\n")

        run_wiki(wiki, ["pull"])

        entries = read_log(wiki, "conflict.jsonl")
        assert any(e["rel_path"] == "src" for e in entries)

    def test_conflict_wiki_strategy_keeps_wiki_content(self, wiki_setup):
        wiki, repo = wiki_setup
        original = (wiki / "docs" / "src" / "CLAUDE.md").read_text()
        (repo / "src" / "CLAUDE.md").unlink()
        (repo / "src" / "CLAUDE.md").write_text("# Repo Version\n")

        run_wiki(wiki, ["pull", "--strategy", "wiki"])

        assert (wiki / "docs" / "src" / "CLAUDE.md").read_text() == original
        assert is_valid_symlink(repo / "src" / "CLAUDE.md")

    def test_conflict_repo_strategy_uses_repo_content(self, wiki_setup):
        wiki, repo = wiki_setup
        (repo / "src" / "CLAUDE.md").unlink()
        (repo / "src" / "CLAUDE.md").write_text("# Repo Version\n")

        run_wiki(wiki, ["pull", "--strategy", "repo"])

        assert "Repo Version" in (wiki / "docs" / "src" / "CLAUDE.md").read_text()
        assert is_valid_symlink(repo / "src" / "CLAUDE.md")

    def test_conflict_wiki_strategy_clears_conflict_log(self, wiki_setup):
        wiki, repo = wiki_setup
        (repo / "src" / "CLAUDE.md").unlink()
        (repo / "src" / "CLAUDE.md").write_text("# Conflict\n")
        run_wiki(wiki, ["pull"])  # creates conflict entry

        run_wiki(wiki, ["pull", "--strategy", "wiki"])

        entries = read_log(wiki, "conflict.jsonl")
        assert not any(e["rel_path"] == "src" for e in entries)
