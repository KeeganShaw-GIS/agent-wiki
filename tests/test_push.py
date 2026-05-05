"""Tests for agent-wiki push command."""

from utils import is_valid_symlink, read_flags, run_wiki, write_schema


class TestPushSymlinks:
    def test_creates_symlinks_for_all_schema_paths(self, wiki_setup):
        wiki, repo = wiki_setup
        assert is_valid_symlink(repo / "CLAUDE.md")
        assert is_valid_symlink(repo / "src" / "CLAUDE.md")
        assert is_valid_symlink(repo / "frontend" / "CLAUDE.md")
        assert is_valid_symlink(repo / "frontend" / "components" / "CLAUDE.md")

    def test_symlinks_resolve_to_wiki_docs(self, wiki_setup):
        wiki, repo = wiki_setup
        src_link = repo / "src" / "CLAUDE.md"
        assert src_link.is_symlink()
        assert src_link.resolve() == (wiki / "docs" / "src" / "CLAUDE.md").resolve()

    def test_creates_wiki_docs_for_all_paths(self, wiki_setup):
        wiki, repo = wiki_setup
        assert (wiki / "docs" / "CLAUDE.md").exists()
        assert (wiki / "docs" / "src" / "CLAUDE.md").exists()
        assert (wiki / "docs" / "frontend" / "CLAUDE.md").exists()
        assert (wiki / "docs" / "frontend" / "components" / "CLAUDE.md").exists()

    def test_new_docs_have_placeholder_content(self, wiki_setup):
        wiki, repo = wiki_setup
        content = (wiki / "docs" / "src" / "CLAUDE.md").read_text()
        assert "Not yet populated" in content

    def test_root_symlink_points_to_wiki_doc(self, wiki_setup):
        wiki, repo = wiki_setup
        root_link = repo / "CLAUDE.md"
        assert root_link.is_symlink()
        assert root_link.resolve() == (wiki / "docs" / "CLAUDE.md").resolve()

    def test_creates_agent_index(self, wiki_setup):
        wiki, repo = wiki_setup
        index = repo / ".agent-wiki" / "AGENT-INDEX.md"
        assert index.exists()
        content = index.read_text()
        # Paths must be relative to .agent-wiki/ (no leading .agent-wiki/)
        assert "symlinks/src.md" in content
        assert ".agent-wiki/symlinks" not in content
        assert "agents/llm.md" in content
        assert ".agent-wiki/agents" not in content

    def test_creates_mirror_symlinks_in_agent_wiki(self, wiki_setup):
        wiki, repo = wiki_setup
        assert is_valid_symlink(repo / ".agent-wiki" / "symlinks" / "src.md")
        assert is_valid_symlink(repo / ".agent-wiki" / "symlinks" / "frontend.md")
        assert is_valid_symlink(repo / ".agent-wiki" / "symlinks" / "frontend-components.md")


class TestPushVerify:
    def test_verify_ok_when_all_symlinks_valid(self, wiki_setup):
        wiki, repo = wiki_setup
        result = run_wiki(wiki, ["push", "--verify"])
        assert "All symlinks OK" in result.stdout

    def test_verify_repairs_missing_symlink(self, wiki_setup):
        wiki, repo = wiki_setup
        broken = repo / "src" / "CLAUDE.md"
        broken.unlink()
        assert not broken.exists()

        run_wiki(wiki, ["push", "--verify"])
        assert is_valid_symlink(broken)

    def test_verify_sets_docs_out_of_sync_flag(self, wiki_setup):
        wiki, repo = wiki_setup
        (repo / "src" / "CLAUDE.md").unlink()
        run_wiki(wiki, ["push", "--verify"])
        flags = read_flags(wiki)
        assert "docs_out_of_sync" in flags

    def test_verify_repairs_dead_symlink(self, wiki_setup):
        wiki, repo = wiki_setup
        link = repo / "src" / "CLAUDE.md"
        # Replace symlink with one pointing to a nonexistent file
        link.unlink()
        link.symlink_to("/nonexistent/path/CLAUDE.md")
        assert not link.resolve().exists()

        run_wiki(wiki, ["push", "--verify"])
        assert is_valid_symlink(link)


class TestVerifyOrphanEject:
    def test_verify_ejects_orphaned_symlink(self, wiki_setup):
        """push --verify removes symlinks with WIKI MANAGED banner not in schema."""
        wiki, repo = wiki_setup

        # Create a directory with a managed symlink outside the schema
        (repo / "orphan").mkdir()
        orphan_wiki_doc = wiki / "docs" / "orphan" / "CLAUDE.md"
        orphan_wiki_doc.parent.mkdir(parents=True, exist_ok=True)
        orphan_wiki_doc.write_text("> **WIKI MANAGED** — orphan\n\n---\n\n# Orphan\n")
        orphan_link = repo / "orphan" / "CLAUDE.md"
        import os
        orphan_link.symlink_to(os.path.relpath(orphan_wiki_doc, orphan_link.parent))

        run_wiki(wiki, ["push", "--verify"])

        # Symlink replaced with real file, banner stripped
        assert orphan_link.exists()
        assert not orphan_link.is_symlink()
        assert "WIKI MANAGED" not in orphan_link.read_text()

    def test_verify_strips_banner_from_orphaned_real_file(self, wiki_setup):
        """push --verify strips WIKI MANAGED banner from a real file not in schema."""
        wiki, repo = wiki_setup

        (repo / "legacy").mkdir()
        legacy = repo / "legacy" / "CLAUDE.md"
        legacy.write_text("> **WIKI MANAGED** — This file is a symlink\n\n---\n\n# Legacy\n")

        run_wiki(wiki, ["push", "--verify"])

        assert legacy.exists()
        assert "WIKI MANAGED" not in legacy.read_text()
        assert "# Legacy" in legacy.read_text()


class TestPushNewEntry:
    def test_adding_schema_path_creates_doc_and_symlink(self, wiki_setup):
        wiki, repo = wiki_setup
        (repo / "api").mkdir()
        write_schema(wiki, "root+:\n  src+:\n  frontend+:\n    components+:\n  api+:\n")
        run_wiki(wiki, ["push"])

        assert (wiki / "docs" / "api" / "CLAUDE.md").exists()
        assert is_valid_symlink(repo / "api" / "CLAUDE.md")

    def test_absorbs_real_file_on_push(self, wiki_setup):
        """If a real file exists at a schema path, push absorbs it into the wiki."""
        wiki, repo = wiki_setup
        (repo / "api").mkdir()
        (repo / "api" / "CLAUDE.md").write_text("# API\nReal content.\n")
        write_schema(wiki, "root+:\n  src+:\n  frontend+:\n    components+:\n  api+:\n")
        run_wiki(wiki, ["push"])

        wiki_doc = wiki / "docs" / "api" / "CLAUDE.md"
        assert wiki_doc.exists()
        assert "Real content" in wiki_doc.read_text()
        assert is_valid_symlink(repo / "api" / "CLAUDE.md")
