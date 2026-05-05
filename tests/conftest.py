"""Shared fixtures for the agent-wiki test suite."""

import json
import shutil
from pathlib import Path

import pytest

from utils import git_cmd, make_commit, run_wiki, write_schema


_RICH_SCHEMA = """\
root+:
  src+:
  frontend+:
    components+:
"""


def _create_target_repo(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    git_cmd(path, "init")
    git_cmd(path, "config", "user.email", "test@test.com")
    git_cmd(path, "config", "user.name", "Test User")

    (path / "README.md").write_text("# Target Repo\n")

    src = path / "src"
    src.mkdir()
    (src / "main.py").write_text("def main():\n    pass\n")
    (src / "utils.py").write_text("def util():\n    pass\n")

    fe = path / "frontend"
    fe.mkdir()
    (fe / "app.ts").write_text("export default {};\n")
    comp = fe / "components"
    comp.mkdir()
    (comp / "Button.tsx").write_text("export const Button = () => null;\n")

    make_commit(path, "initial commit")
    return path


# ── Session-scoped templates (built once, copied per test) ───────────────────

@pytest.fixture(scope="session")
def _no_hooks_template(tmp_path_factory):
    """Build one canonical no-hooks wiki+repo; each test gets a fresh copy."""
    base = tmp_path_factory.mktemp("tmpl_no_hooks")
    repo = _create_target_repo(base / "target")
    wiki = base / "wiki"
    wiki.mkdir()
    run_wiki(wiki, [
        "init", "--repo-path", str(repo),
        "--doc-filename", "CLAUDE.md",
        "--no-hooks", "--no-detect-target-docs",
    ])
    write_schema(wiki, _RICH_SCHEMA)
    run_wiki(wiki, ["push"])
    return base


@pytest.fixture(scope="session")
def _hooked_template(tmp_path_factory):
    """Build one canonical hooked wiki+repo; each test gets a fresh copy."""
    base = tmp_path_factory.mktemp("tmpl_hooked")
    repo = _create_target_repo(base / "target")
    wiki = base / "wiki"
    wiki.mkdir()
    run_wiki(wiki, [
        "init", "--repo-path", str(repo),
        "--doc-filename", "CLAUDE.md",
        "--no-detect-target-docs",
    ])
    write_schema(wiki, _RICH_SCHEMA)
    run_wiki(wiki, ["push"])
    return base


def _copy_template(base: Path, tmp_path: Path):
    """Copy a template base dir, fix absolute paths in config/wiki-path."""
    dest = tmp_path / "base"
    shutil.copytree(base, dest, symlinks=True)
    wiki = dest / "wiki"
    repo = dest / "target"

    # Update config.json → repo_path now points to the copy
    cfg = wiki / "config.json"
    config = json.loads(cfg.read_text())
    config["repo_path"] = str(repo)
    cfg.write_text(json.dumps(config, indent=2) + "\n")

    # Update .agent-wiki/wiki-path if present (hooked setup)
    wiki_path_file = repo / ".agent-wiki" / "wiki-path"
    if wiki_path_file.exists():
        wiki_path_file.write_text(str(wiki) + "\n")

    return wiki, repo


# ── Per-test fixtures ─────────────────────────────────────────────────────────

@pytest.fixture
def target_repo(tmp_path):
    return _create_target_repo(tmp_path / "target")


@pytest.fixture
def wiki_dir(tmp_path):
    w = tmp_path / "wiki"
    w.mkdir()
    return w


@pytest.fixture
def wiki_setup(tmp_path, _no_hooks_template):
    """Fresh copy of the initialized no-hooks wiki+repo for each test."""
    return _copy_template(_no_hooks_template, tmp_path)


@pytest.fixture
def wiki_hooked(tmp_path, _hooked_template):
    """Fresh copy of the initialized hooked wiki+repo for each test."""
    return _copy_template(_hooked_template, tmp_path)
