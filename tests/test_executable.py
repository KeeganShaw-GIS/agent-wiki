"""Smoke tests for the installed agent-wiki executable.

A session-scoped fixture installs the package into a fresh venv so these tests
exercise the real entry point, not python -m wiki.cli.
"""

import subprocess
import sys
import venv
from pathlib import Path

import pytest

_PROJECT_ROOT = Path(__file__).parent.parent
_COMMANDS = ["init", "push", "pull", "detect-drift", "eject", "status", "add-agent", "clear-flags"]


@pytest.fixture(scope="session")
def installed_bin(tmp_path_factory):
    """Install agent-wiki into a throwaway venv; return the binary path."""
    venv_dir = tmp_path_factory.mktemp("install_venv")
    venv.create(str(venv_dir), with_pip=True)

    pip = venv_dir / "bin" / "pip"
    result = subprocess.run(
        [str(pip), "install", str(_PROJECT_ROOT)],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        pytest.fail(f"pip install failed:\n{result.stderr}")

    return venv_dir / "bin" / "agent-wiki"


class TestInstalledExecutable:
    def test_binary_exists(self, installed_bin):
        assert installed_bin.exists(), f"agent-wiki binary not found at {installed_bin}"

    def test_help_exits_zero(self, installed_bin):
        result = subprocess.run([str(installed_bin), "--help"], capture_output=True, text=True)
        assert result.returncode == 0

    def test_help_lists_all_commands(self, installed_bin):
        result = subprocess.run([str(installed_bin), "--help"], capture_output=True, text=True)
        for cmd in _COMMANDS:
            assert cmd in result.stdout, f"command '{cmd}' missing from --help output"

    def test_init_subcommand_help(self, installed_bin):
        result = subprocess.run(
            [str(installed_bin), "init", "--help"], capture_output=True, text=True
        )
        assert result.returncode == 0
        assert "--repo-path" in result.stdout

    def test_push_subcommand_help(self, installed_bin):
        result = subprocess.run(
            [str(installed_bin), "push", "--help"], capture_output=True, text=True
        )
        assert result.returncode == 0
        assert "--verify" in result.stdout

    def test_unknown_command_exits_nonzero(self, installed_bin):
        result = subprocess.run(
            [str(installed_bin), "not-a-command"], capture_output=True, text=True
        )
        assert result.returncode != 0
