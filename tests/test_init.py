"""Tests for agent-wiki init command."""

import json
from pathlib import Path

from utils import git_cmd, is_valid_symlink, make_commit, run_wiki


class TestInitBasic:
    def test_creates_config_json(self, target_repo, wiki_dir):
        run_wiki(wiki_dir, [
            "init", "--repo-path", str(target_repo),
            "--doc-filename", "CLAUDE.md",
            "--no-hooks", "--no-detect-target-docs",
        ])
        config = json.loads((wiki_dir / "config.json").read_text())
        assert config["repo_path"] == str(target_repo)
        assert config["doc_filename"] == "CLAUDE.md"
        assert config["skip_worktree"] is True

    def test_creates_flags_json(self, target_repo, wiki_dir):
        run_wiki(wiki_dir, [
            "init", "--repo-path", str(target_repo),
            "--doc-filename", "CLAUDE.md",
            "--no-hooks", "--no-detect-target-docs",
        ])
        flags_file = wiki_dir / "logs" / "flags.json"
        assert flags_file.exists()
        assert json.loads(flags_file.read_text()) == {}

    def test_creates_schema_yaml(self, target_repo, wiki_dir):
        run_wiki(wiki_dir, [
            "init", "--repo-path", str(target_repo),
            "--doc-filename", "CLAUDE.md",
            "--no-hooks", "--no-detect-target-docs",
        ])
        schema = wiki_dir / "schema.yaml"
        assert schema.exists()
        assert "root+" in schema.read_text()

    def test_creates_template_files(self, target_repo, wiki_dir):
        run_wiki(wiki_dir, [
            "init", "--repo-path", str(target_repo),
            "--doc-filename", "CLAUDE.md",
            "--no-hooks", "--no-detect-target-docs",
        ])
        assert (wiki_dir / "llm.md").exists()
        assert (wiki_dir / "wiki-instructions.md").exists()
        assert (wiki_dir / "templates" / "instructions.md").exists()
        assert (wiki_dir / "templates" / "WIKI_UPDATE.md").exists()
        assert (wiki_dir / "templates" / "WIKI_MERGE.md").exists()

    def test_root_doc_uses_instructions_as_fallback(self, target_repo, wiki_dir):
        """Root CLAUDE.md content comes from instructions.md when repo has no existing doc."""
        run_wiki(wiki_dir, [
            "init", "--repo-path", str(target_repo),
            "--doc-filename", "CLAUDE.md",
            "--no-hooks", "--no-detect-target-docs",
        ])
        root_doc = wiki_dir / "docs" / "CLAUDE.md"
        assert root_doc.exists()
        instructions_content = (wiki_dir / "templates" / "instructions.md").read_text()
        root_content = root_doc.read_text()
        # Header must be present
        assert "<!-- agent-wiki" in root_content
        # instructions.md content must be the body
        assert instructions_content.strip() in root_content

    def test_root_doc_has_wiki_managed_banner(self, target_repo, wiki_dir):
        """Root doc always has the agent-wiki header even on a fresh repo."""
        run_wiki(wiki_dir, [
            "init", "--repo-path", str(target_repo),
            "--doc-filename", "CLAUDE.md",
            "--no-hooks", "--no-detect-target-docs",
        ])
        root_doc = wiki_dir / "docs" / "CLAUDE.md"
        assert "<!-- agent-wiki" in root_doc.read_text()

    def test_creates_root_doc(self, target_repo, wiki_dir):
        run_wiki(wiki_dir, [
            "init", "--repo-path", str(target_repo),
            "--doc-filename", "CLAUDE.md",
            "--no-hooks", "--no-detect-target-docs",
        ])
        assert (wiki_dir / "docs" / "CLAUDE.md").exists()

    def test_creates_root_symlink_in_target(self, target_repo, wiki_dir):
        run_wiki(wiki_dir, [
            "init", "--repo-path", str(target_repo),
            "--doc-filename", "CLAUDE.md",
            "--no-hooks", "--no-detect-target-docs",
        ])
        link = target_repo / "CLAUDE.md"
        assert link.is_symlink()

    def test_no_hooks_flag_skips_hooks(self, target_repo, wiki_dir):
        run_wiki(wiki_dir, [
            "init", "--repo-path", str(target_repo),
            "--doc-filename", "CLAUDE.md",
            "--no-hooks", "--no-detect-target-docs",
        ])
        assert not (target_repo / ".git" / "hooks" / "pre-commit").exists()
        assert not (target_repo / ".git" / "hooks" / "post-checkout").exists()


class TestInitHooks:
    def test_creates_pre_commit_hook(self, target_repo, wiki_dir):
        run_wiki(wiki_dir, [
            "init", "--repo-path", str(target_repo),
            "--doc-filename", "CLAUDE.md",
            "--no-detect-target-docs",
        ])
        hook = target_repo / ".git" / "hooks" / "pre-commit"
        assert hook.exists()
        assert hook.stat().st_mode & 0o111
        assert "agent-wiki" in hook.read_text()

    def test_creates_post_checkout_hook(self, target_repo, wiki_dir):
        run_wiki(wiki_dir, [
            "init", "--repo-path", str(target_repo),
            "--doc-filename", "CLAUDE.md",
            "--no-detect-target-docs",
        ])
        hook = target_repo / ".git" / "hooks" / "post-checkout"
        assert hook.exists()
        assert hook.stat().st_mode & 0o111
        assert "agent-wiki" in hook.read_text()

    def test_creates_agent_wiki_dir(self, target_repo, wiki_dir):
        run_wiki(wiki_dir, [
            "init", "--repo-path", str(target_repo),
            "--doc-filename", "CLAUDE.md",
            "--no-detect-target-docs",
        ])
        aw = target_repo / ".agent-wiki"
        assert aw.exists()
        assert (aw / "wiki").exists()
        assert (aw / "wiki").stat().st_mode & 0o111
        assert (aw / "wiki-path").exists()
        assert (aw / "schema.yaml").is_symlink()
        assert (aw / "flags.json").is_symlink()
        assert (aw / "agents").is_dir()

    def test_wiki_path_file_points_to_wiki(self, target_repo, wiki_dir):
        run_wiki(wiki_dir, [
            "init", "--repo-path", str(target_repo),
            "--doc-filename", "CLAUDE.md",
            "--no-detect-target-docs",
        ])
        wiki_path = (target_repo / ".agent-wiki" / "wiki-path").read_text().strip()
        assert wiki_path == str(wiki_dir)

    def test_gitignore_has_agent_wiki(self, target_repo, wiki_dir):
        run_wiki(wiki_dir, [
            "init", "--repo-path", str(target_repo),
            "--doc-filename", "CLAUDE.md",
            "--no-detect-target-docs",
        ])
        gitignore = target_repo / ".gitignore"
        assert gitignore.exists()
        assert ".agent-wiki" in gitignore.read_text()


class TestInitAbsorbExistingDocs:
    def test_existing_root_doc_absorbed_as_symlink(self, target_repo, wiki_dir):
        """Existing CLAUDE.md at repo root is absorbed; target becomes a symlink."""
        (target_repo / "CLAUDE.md").write_text("# My Project\nExisting content.\n")
        make_commit(target_repo, "add CLAUDE.md")

        run_wiki(wiki_dir, [
            "init", "--repo-path", str(target_repo),
            "--doc-filename", "CLAUDE.md",
            "--no-hooks",
        ])

        assert is_valid_symlink(target_repo / "CLAUDE.md")
        wiki_doc = wiki_dir / "docs" / "CLAUDE.md"
        assert wiki_doc.exists()
        assert "My Project" in wiki_doc.read_text()

    def test_existing_nested_doc_absorbed(self, target_repo, wiki_dir):
        """Existing CLAUDE.md in a subdirectory is absorbed and path added to schema."""
        (target_repo / "src" / "CLAUDE.md").write_text("# Source\nAbout src.\n")
        make_commit(target_repo, "add src/CLAUDE.md")

        run_wiki(wiki_dir, [
            "init", "--repo-path", str(target_repo),
            "--doc-filename", "CLAUDE.md",
            "--no-hooks",
        ])

        assert is_valid_symlink(target_repo / "src" / "CLAUDE.md")
        wiki_doc = wiki_dir / "docs" / "src" / "CLAUDE.md"
        assert wiki_doc.exists()
        assert "Source" in wiki_doc.read_text()

    def test_absorbed_doc_updates_schema(self, target_repo, wiki_dir):
        (target_repo / "src" / "CLAUDE.md").write_text("# Source\n")
        make_commit(target_repo, "add src/CLAUDE.md")

        run_wiki(wiki_dir, [
            "init", "--repo-path", str(target_repo),
            "--doc-filename", "CLAUDE.md",
            "--no-hooks",
        ])

        schema = (wiki_dir / "schema.yaml").read_text()
        assert "src+" in schema

    def test_absorbed_doc_gets_metadata_footer(self, target_repo, wiki_dir):
        (target_repo / "src" / "CLAUDE.md").write_text("# Source\n")
        make_commit(target_repo, "add src/CLAUDE.md")

        run_wiki(wiki_dir, [
            "init", "--repo-path", str(target_repo),
            "--doc-filename", "CLAUDE.md",
            "--no-hooks",
        ])

        from utils import read_footer
        footer = read_footer(wiki_dir / "docs" / "src" / "CLAUDE.md")
        assert "Location" in footer
        assert "LastTouchedBy" in footer
