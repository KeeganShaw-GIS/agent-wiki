"""Test utilities for the agent-wiki test suite."""

import json
import os
import subprocess
import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).parent.parent
# Always run from source so tests exercise the current code, not a stale install.
_WIKI_CMD = [sys.executable, "-m", "wiki.cli"]


def run_wiki(cwd: Path, args: list, *, check: bool = True) -> subprocess.CompletedProcess:
    """Run agent-wiki from the given wiki root directory."""
    env = os.environ.copy()
    env["PYTHONPATH"] = str(_PROJECT_ROOT) + os.pathsep + env.get("PYTHONPATH", "")

    result = subprocess.run(
        _WIKI_CMD + args,
        cwd=str(cwd),
        capture_output=True,
        text=True,
        env=env,
    )
    if check and result.returncode != 0:
        msg = (result.stdout + "\n" + result.stderr).strip()
        raise AssertionError(
            f"agent-wiki {' '.join(args)} failed (exit {result.returncode}):\n{msg}"
        )
    return result


def git_cmd(repo: Path, *args, check: bool = True) -> subprocess.CompletedProcess:
    """Run a git command in repo."""
    return subprocess.run(
        ["git", "-C", str(repo)] + list(args),
        capture_output=True,
        text=True,
        check=check,
    )


def make_commit(repo: Path, message: str = "test commit"):
    """Stage everything and commit."""
    git_cmd(repo, "add", ".")
    git_cmd(repo, "commit", "-m", message)


def read_flags(wiki: Path) -> dict:
    """Read logs/flags.json from a wiki directory."""
    flags_file = wiki / "logs" / "flags.json"
    if not flags_file.exists():
        return {}
    return json.loads(flags_file.read_text())


def read_log(wiki: Path, name: str) -> list:
    """Read a JSONL log file (e.g. 'drift.jsonl') from logs/."""
    log_file = wiki / "logs" / name
    if not log_file.exists():
        return []
    entries = []
    for line in log_file.read_text().strip().split("\n"):
        line = line.strip()
        if line:
            entries.append(json.loads(line))
    return entries


def read_footer(path: Path) -> dict:
    """Parse the agent-wiki-meta footer from a doc file, returning key→value dict."""
    if not path.exists():
        return {}
    content = path.read_text()
    marker = "<!-- agent-wiki-meta"
    end_marker = "-->"
    start = content.find(marker)
    if start == -1:
        return {}
    end = content.find(end_marker, start)
    if end == -1:
        return {}
    block = content[start + len(marker):end]
    result = {}
    for line in block.strip().splitlines():
        if ":" in line:
            k, _, v = line.partition(":")
            result[k.strip()] = v.strip()
    return result


def is_valid_symlink(path: Path) -> bool:
    """True if path is a symlink that resolves to an existing file."""
    return path.is_symlink() and path.resolve().exists()


def write_schema(wiki: Path, content: str):
    """Overwrite schema.yaml in a wiki directory."""
    (wiki / "schema.yaml").write_text(content)
