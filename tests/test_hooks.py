"""Tests for hook installation, behavior, and add-agent command."""

from utils import git_cmd, is_valid_symlink, read_log, run_wiki


class TestHookInstallation:
    def test_pre_commit_hook_is_executable(self, wiki_hooked):
        wiki, repo = wiki_hooked
        hook = repo / ".git" / "hooks" / "pre-commit"
        assert hook.exists()
        assert hook.stat().st_mode & 0o111

    def test_post_checkout_hook_is_executable(self, wiki_hooked):
        wiki, repo = wiki_hooked
        hook = repo / ".git" / "hooks" / "post-checkout"
        assert hook.exists()
        assert hook.stat().st_mode & 0o111

    def test_pre_commit_calls_detect_drift(self, wiki_hooked):
        wiki, repo = wiki_hooked
        text = (repo / ".git" / "hooks" / "pre-commit").read_text()
        assert "detect-drift" in text

    def test_post_checkout_calls_push(self, wiki_hooked):
        wiki, repo = wiki_hooked
        text = (repo / ".git" / "hooks" / "post-checkout").read_text()
        assert "push" in text

    def test_wrapper_script_is_executable(self, wiki_hooked):
        wiki, repo = wiki_hooked
        wrapper = repo / ".agent-wiki" / "wiki"
        assert wrapper.exists()
        assert wrapper.stat().st_mode & 0o111

    def test_wrapper_script_reads_wiki_path(self, wiki_hooked):
        wiki, repo = wiki_hooked
        script = (repo / ".agent-wiki" / "wiki").read_text()
        assert "wiki-path" in script

    def test_agents_dir_has_llm_md_symlink(self, wiki_hooked):
        wiki, repo = wiki_hooked
        llm = repo / ".agent-wiki" / "agents" / "llm.md"
        assert is_valid_symlink(llm)

    def test_agents_dir_has_update_guide(self, wiki_hooked):
        wiki, repo = wiki_hooked
        assert is_valid_symlink(repo / ".agent-wiki" / "agents" / "WIKI_UPDATE.md")

    def test_agents_dir_has_merge_guide(self, wiki_hooked):
        wiki, repo = wiki_hooked
        assert is_valid_symlink(repo / ".agent-wiki" / "agents" / "WIKI_MERGE.md")


class TestPreCommitHook:
    def test_pre_commit_is_non_blocking(self, wiki_hooked):
        """Hook must exit 0 so it never prevents a commit."""
        wiki, repo = wiki_hooked
        (repo / "src" / "main.py").write_text("# modified\n")
        git_cmd(repo, "add", ".")
        result = git_cmd(repo, "commit", "-m", "test non-blocking")
        assert result.returncode == 0

    def test_pre_commit_captures_drift_on_repeated_edits(self, wiki_hooked):
        """Pre-commit detects drift when a file changed since SourceCommitID is staged again."""
        wiki, repo = wiki_hooked

        # Commit 1: change src/main.py (SourceCommitID is the initial commit, HEAD moves to this)
        (repo / "src" / "main.py").write_text("def main(): return 1\n")
        git_cmd(repo, "add", "src/main.py")
        git_cmd(repo, "commit", "-m", "v2")

        # Commit 2: change src/main.py again — pre-commit fires and sees src drift
        (repo / "src" / "main.py").write_text("def main(): return 2\n")
        git_cmd(repo, "add", "src/main.py")
        git_cmd(repo, "commit", "-m", "v3")

        entries = read_log(wiki, "drift.jsonl")
        assert any(e.get("rel_path") == "src" for e in entries)

    def test_pre_commit_only_logs_staged_path(self, wiki_hooked):
        """Drift is only logged for paths that are BOTH drifted AND staged."""
        wiki, repo = wiki_hooked

        # Commit 1: change src/ — src now has drift vs SourceCommitID
        (repo / "src" / "main.py").write_text("def main(): return 1\n")
        git_cmd(repo, "add", "src/main.py")
        git_cmd(repo, "commit", "-m", "src change")

        # Commit 2: change frontend/ — frontend now also has drift vs SourceCommitID
        (repo / "frontend" / "app.ts").write_text("export const x = 1;\n")
        git_cmd(repo, "add", "frontend/app.ts")
        git_cmd(repo, "commit", "-m", "frontend change")

        # Commit 3: stage ONLY frontend again — pre-commit fires, detects frontend (staged+drifted)
        # src is drifted but NOT staged, so it must NOT appear in the drift log
        (repo / "frontend" / "app.ts").write_text("export const x = 2;\n")
        (repo / "src" / "main.py").write_text("def main(): return 2\n")
        git_cmd(repo, "add", "frontend/app.ts")
        git_cmd(repo, "commit", "-m", "frontend only")

        entries = read_log(wiki, "drift.jsonl")
        staged_rel_paths = [e["rel_path"] for e in entries]
        assert "frontend" in staged_rel_paths
        assert "src" not in staged_rel_paths


class TestPostCheckoutHook:
    def test_post_checkout_restores_missing_symlinks(self, wiki_hooked):
        """After a branch switch, the post-checkout hook restores broken symlinks."""
        wiki, repo = wiki_hooked

        # Create and switch to a new branch
        git_cmd(repo, "checkout", "-b", "feature")

        # Remove a symlink while on the feature branch
        src_link = repo / "src" / "CLAUDE.md"
        src_link.unlink()
        assert not src_link.exists()

        # Switch back — post-checkout hook fires and runs push
        git_cmd(repo, "checkout", "-")

        assert is_valid_symlink(src_link)

    def test_post_checkout_is_non_blocking(self, wiki_hooked):
        """post-checkout hook exits 0 regardless."""
        wiki, repo = wiki_hooked
        git_cmd(repo, "checkout", "-b", "another")
        result = git_cmd(repo, "checkout", "-")
        assert result.returncode == 0


class TestAddAgent:
    def test_add_agent_creates_file(self, wiki_hooked):
        wiki, repo = wiki_hooked
        run_wiki(wiki, ["add-agent", "--name", "researcher"])
        agent_file = repo / ".agent-wiki" / "agents" / "researcher.md"
        assert agent_file.exists()

    def test_add_agent_creates_real_file_not_symlink(self, wiki_hooked):
        wiki, repo = wiki_hooked
        run_wiki(wiki, ["add-agent", "--name", "planner"])
        agent_file = repo / ".agent-wiki" / "agents" / "planner.md"
        assert agent_file.exists()
        assert not agent_file.is_symlink()

    def test_add_agent_appends_md_extension(self, wiki_hooked):
        wiki, repo = wiki_hooked
        run_wiki(wiki, ["add-agent", "--name", "reviewer"])
        assert (repo / ".agent-wiki" / "agents" / "reviewer.md").exists()
        # Should not create double extension
        assert not (repo / ".agent-wiki" / "agents" / "reviewer.md.md").exists()

    def test_add_agent_with_md_extension_works(self, wiki_hooked):
        wiki, repo = wiki_hooked
        run_wiki(wiki, ["add-agent", "--name", "analyst.md"])
        assert (repo / ".agent-wiki" / "agents" / "analyst.md").exists()

    def test_add_agent_is_idempotent(self, wiki_hooked):
        wiki, repo = wiki_hooked
        run_wiki(wiki, ["add-agent", "--name", "researcher"])
        run_wiki(wiki, ["add-agent", "--name", "researcher"])  # second call is a no-op
        assert (repo / ".agent-wiki" / "agents" / "researcher.md").exists()
