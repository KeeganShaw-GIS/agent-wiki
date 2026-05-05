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

    def test_pull_strips_stale_banner_from_copied_doc(self, wiki_setup):
        """A real file with a wiki header referencing a different path gets
        the header stripped and re-absorbed with a fresh header for its actual path."""
        wiki, repo = wiki_setup

        # Simulate copy-paste: file at api/ has a header claiming it lives at src/
        (repo / "api").mkdir(exist_ok=True)
        (repo / "api" / "CLAUDE.md").write_text(
            "<!-- agent-wiki\n"
            "Location: src/CLAUDE.md\n"
            "LastTouchedBy: agent-wiki push\n"
            "-->\n\n"
            "# API\nPasted from src.\n"
        )

        run_wiki(wiki, ["pull"])

        wiki_doc = wiki / "docs" / "api" / "CLAUDE.md"
        content = wiki_doc.read_text()
        # Old Location stripped — not present in body
        assert "src/CLAUDE.md" not in content
        # Content preserved
        assert "Pasted from src" in content
        # Fresh header written for actual path
        from utils import read_footer
        footer = read_footer(wiki_doc)
        assert footer.get("Location", "").endswith("api/CLAUDE.md")

    def test_pull_strips_banner_even_when_location_matches(self, wiki_setup):
        """Header is always stripped on pull — even if Location is correct.
        The wiki rewrites a fresh authoritative header."""
        wiki, repo = wiki_setup
        (repo / "src" / "CLAUDE.md").unlink()
        (repo / "src" / "CLAUDE.md").write_text(
            "<!-- agent-wiki\nLocation: src/CLAUDE.md\nLastTouchedBy: agent-wiki push\n-->\n\n"
            "# Src content\n"
        )

        run_wiki(wiki, ["pull"])

        content = (wiki / "docs" / "src" / "CLAUDE.md").read_text()
        assert "# Src content" in content
        # Only one header block (the fresh one written by pull)
        assert content.count("<!-- agent-wiki") == 1

    def test_no_unmanaged_docs_prints_nothing_found(self, wiki_setup):
        wiki, repo = wiki_setup
        result = run_wiki(wiki, ["pull"])
        assert "No unmanaged" in result.stdout

    def test_root_doc_absorbed_gets_wiki_header(self, wiki_setup):
        """A root CLAUDE.md absorbed by pull gets the agent-wiki header."""
        wiki, repo = wiki_setup
        # Remove the existing root symlink and place a real file
        (repo / "CLAUDE.md").unlink()
        (repo / "CLAUDE.md").write_text("# Project Root\nContent.\n")

        run_wiki(wiki, ["pull", "--strategy", "repo"])

        content = (wiki / "docs" / "CLAUDE.md").read_text()
        assert "<!-- agent-wiki" in content


class TestPullConflicts:
    def test_default_pull_repo_wins(self, wiki_setup):
        """Default pull (repo wins) absorbs repo file and sets multiple_versions flag."""
        wiki, repo = wiki_setup
        (repo / "src" / "CLAUDE.md").unlink()
        (repo / "src" / "CLAUDE.md").write_text("# Repo Edit\n")

        run_wiki(wiki, ["pull"])

        assert "Repo Edit" in (wiki / "docs" / "src" / "CLAUDE.md").read_text()
        assert is_valid_symlink(repo / "src" / "CLAUDE.md")
        assert read_flags(wiki).get("multiple_versions") is True

    def test_default_pull_backs_up_old_wiki_version(self, wiki_setup):
        """Default pull saves previous wiki content to logs/local-edits/."""
        wiki, repo = wiki_setup
        original = (wiki / "docs" / "src" / "CLAUDE.md").read_text()
        (repo / "src" / "CLAUDE.md").unlink()
        (repo / "src" / "CLAUDE.md").write_text("# Repo Edit\n")

        run_wiki(wiki, ["pull"])

        backup = wiki / "logs" / "local-edits" / "src.md"
        assert backup.exists()
        assert backup.read_text() == original

    def test_conflict_skip_strategy_sets_flag(self, wiki_setup):
        wiki, repo = wiki_setup
        (repo / "src" / "CLAUDE.md").unlink()
        (repo / "src" / "CLAUDE.md").write_text("# Conflict\n")

        run_wiki(wiki, ["pull", "--strategy", "skip"])

        assert read_flags(wiki).get("multiple_versions") is True

    def test_conflict_skip_strategy_logs_conflict(self, wiki_setup):
        wiki, repo = wiki_setup
        (repo / "src" / "CLAUDE.md").unlink()
        (repo / "src" / "CLAUDE.md").write_text("# Conflict\n")

        run_wiki(wiki, ["pull", "--strategy", "skip"])

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

    def test_conflict_wiki_strategy_clears_conflict_log(self, wiki_setup):
        wiki, repo = wiki_setup
        (repo / "src" / "CLAUDE.md").unlink()
        (repo / "src" / "CLAUDE.md").write_text("# Conflict\n")
        run_wiki(wiki, ["pull", "--strategy", "skip"])

        run_wiki(wiki, ["pull", "--strategy", "wiki"])

        entries = read_log(wiki, "conflict.jsonl")
        assert not any(e["rel_path"] == "src" for e in entries)
