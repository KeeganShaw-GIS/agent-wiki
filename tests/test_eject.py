"""Tests for agent-wiki eject command."""

from utils import is_valid_symlink, run_wiki


class TestEjectScoped:
    def test_eject_scope_replaces_symlink_with_real_file(self, wiki_setup):
        wiki, repo = wiki_setup
        src_link = repo / "src" / "CLAUDE.md"
        assert src_link.is_symlink()

        run_wiki(wiki, ["eject", "--scope", "src"])

        assert src_link.exists()
        assert not src_link.is_symlink()

    def test_ejected_file_has_no_metadata_footer(self, wiki_setup):
        wiki, repo = wiki_setup
        run_wiki(wiki, ["eject", "--scope", "src"])

        content = (repo / "src" / "CLAUDE.md").read_text()
        assert "<!-- agent-wiki-meta" not in content

    def test_ejected_file_has_no_wiki_banner(self, wiki_setup):
        wiki, repo = wiki_setup
        run_wiki(wiki, ["eject", "--scope", "src"])

        content = (repo / "src" / "CLAUDE.md").read_text()
        assert "WIKI MANAGED" not in content

    def test_eject_scope_leaves_other_paths_intact(self, wiki_setup):
        wiki, repo = wiki_setup
        run_wiki(wiki, ["eject", "--scope", "src"])

        # Only src is ejected; others remain symlinks
        assert not (repo / "src" / "CLAUDE.md").is_symlink()
        assert is_valid_symlink(repo / "frontend" / "CLAUDE.md")
        assert is_valid_symlink(repo / "frontend" / "components" / "CLAUDE.md")

    def test_eject_scope_preserves_wiki_doc(self, wiki_setup):
        """Ejecting a path leaves the wiki doc in docs/ intact."""
        wiki, repo = wiki_setup
        wiki_doc = wiki / "docs" / "src" / "CLAUDE.md"
        assert wiki_doc.exists()

        run_wiki(wiki, ["eject", "--scope", "src"])

        assert wiki_doc.exists()

    def test_eject_invalid_scope_exits_nonzero(self, wiki_setup):
        wiki, repo = wiki_setup
        result = run_wiki(wiki, ["eject", "--scope", "nonexistent"], check=False)
        assert result.returncode != 0

    def test_eject_pushes_restores_symlink(self, wiki_setup):
        """After ejecting, running push re-creates the symlink (wiki still manages it)."""
        wiki, repo = wiki_setup
        run_wiki(wiki, ["eject", "--scope", "src"])
        assert not (repo / "src" / "CLAUDE.md").is_symlink()

        run_wiki(wiki, ["push"])

        assert is_valid_symlink(repo / "src" / "CLAUDE.md")


class TestEjectAll:
    def test_eject_all_replaces_all_symlinks(self, wiki_hooked):
        wiki, repo = wiki_hooked
        run_wiki(wiki, ["eject"])

        for rel in ["src", "frontend", "frontend/components"]:
            path = repo
            for part in rel.split("/"):
                path = path / part
            doc = path / "CLAUDE.md"
            assert doc.exists()
            assert not doc.is_symlink()

    def test_eject_all_removes_agent_wiki_dir(self, wiki_hooked):
        wiki, repo = wiki_hooked
        run_wiki(wiki, ["eject"])

        assert not (repo / ".agent-wiki").exists()

    def test_eject_all_backs_up_hooks(self, wiki_hooked):
        wiki, repo = wiki_hooked
        run_wiki(wiki, ["eject"])

        # Hooks should be renamed to .agent-wiki.bak, not deleted
        pre = repo / ".git" / "hooks" / "pre-commit.agent-wiki.bak"
        post = repo / ".git" / "hooks" / "post-checkout.agent-wiki.bak"
        assert pre.exists()
        assert post.exists()

    def test_eject_all_creates_docs_backup(self, wiki_hooked):
        wiki, repo = wiki_hooked
        run_wiki(wiki, ["eject"])

        assert (wiki / "docs.bak").exists()
        assert (wiki / "docs.bak" / "CLAUDE.md").exists()
