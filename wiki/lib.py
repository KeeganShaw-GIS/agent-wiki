"""Shared utilities for the agent-wiki package."""

import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

WIKI_ROOT = Path.cwd()
SCHEMA_FILE = WIKI_ROOT / "schema.yaml"
CONFIG_FILE = WIKI_ROOT / "config.json"
DOCS_ROOT = WIKI_ROOT / "docs"
TEMPLATE_FILE = WIKI_ROOT / "templates" / "AGENT.template.md"
INSTRUCTIONS_FILE = WIKI_ROOT / "templates" / "instructions.md"
WIKI_UPDATE_FILE = WIKI_ROOT / "templates" / "WIKI_UPDATE.md"
WIKI_MERGE_FILE = WIKI_ROOT / "templates" / "WIKI_MERGE.md"
DRIFT_LOG = WIKI_ROOT / "logs" / "drift.jsonl"
SYNC_LOG = WIKI_ROOT / "logs" / "sync.jsonl"
NEW_ENTRY_LOG = WIKI_ROOT / "logs" / "new-entry.jsonl"
CONFLICT_LOG = WIKI_ROOT / "logs" / "conflict.jsonl"
FLAGS_FILE = WIKI_ROOT / "logs" / "flags.json"


# ── Config ───────────────────────────────────────────────────────────────────

def load_config() -> dict:
    if not CONFIG_FILE.exists():
        raise SystemExit(
            "No config.json found. Run:\n"
            "  agent-wiki init --repo-path <path>"
        )
    return json.loads(CONFIG_FILE.read_text())


def save_config(config: dict):
    CONFIG_FILE.write_text(json.dumps(config, indent=2) + "\n")


def get_config_flag(key: str, default=True) -> bool:
    try:
        return bool(load_config().get(key, default))
    except SystemExit:
        return default


AGENT_INDEX_FILENAME = "AGENT-INDEX.md"


def get_doc_filename() -> str:
    try:
        return load_config().get("doc_filename", "CLAUDE.md")
    except SystemExit:
        return "CLAUDE.md"


def get_repo_path() -> Path:
    config = load_config()
    p = Path(config["repo_path"])
    if not p.exists():
        raise SystemExit(
            f"Target repo not found at: {p}\n"
            "Update repo_path in config.json or re-run init."
        )
    return p


# ── Schema ───────────────────────────────────────────────────────────────────

def _parse_yaml_schema(text: str) -> dict:
    root: dict = {}
    stack: list[tuple[int, dict]] = [(-2, root)]
    for line in text.split("\n"):
        stripped = line.rstrip()
        if not stripped or stripped.lstrip().startswith("#"):
            continue
        indent = len(stripped) - len(stripped.lstrip())
        key = stripped.strip().rstrip(":")
        while stack[-1][0] >= indent:
            stack.pop()
        node: dict = {}
        stack[-1][1][key] = node
        stack.append((indent, node))
    return root


def _dump_yaml_schema(node: dict, indent: int = 0) -> str:
    lines = []
    pad = "  " * indent
    for key, value in node.items():
        lines.append(f"{pad}{key}:")
        if isinstance(value, dict) and value:
            lines.append(_dump_yaml_schema(value, indent + 1))
    return "\n".join(lines)


def load_schema() -> dict:
    if not SCHEMA_FILE.exists():
        raise SystemExit("schema.yaml not found in wiki root.")
    return _parse_yaml_schema(SCHEMA_FILE.read_text())


def save_schema(schema: dict):
    fn = get_doc_filename()
    header = (
        f"# Keys ending with + have a {fn} in docs/ and a symlink in the target.\n"
        "# Keys ending with ~ are explicitly untracked (real file stays in target).\n"
        "# Keys without a suffix are structural only (nesting containers, no doc).\n"
    )
    SCHEMA_FILE.write_text(header + _dump_yaml_schema(schema) + "\n")


def _node_suffix(raw_key: str) -> tuple[str, str]:
    for suffix in ("+", "~"):
        if raw_key.endswith(suffix):
            return raw_key[:-1], suffix
    return raw_key, ""


def walk_schema(schema: dict, prefix: str = "") -> list[tuple[str, dict]]:
    results = []
    for raw_key, value in schema.items():
        segment, suffix = _node_suffix(raw_key)
        path = "" if segment == "root" else (f"{prefix}/{segment}" if prefix else segment)
        if suffix == "+":
            results.append((path, value or {}))
        if suffix != "~" and isinstance(value, dict) and value:
            results.extend(walk_schema(value, path))
    return results


def untracked_paths(schema: dict, prefix: str = "") -> list[str]:
    results = []
    for raw_key, value in schema.items():
        segment, suffix = _node_suffix(raw_key)
        path = "" if segment == "root" else (f"{prefix}/{segment}" if prefix else segment)
        if suffix == "~":
            results.append(path)
            if isinstance(value, dict) and value:
                results.extend(untracked_paths(value, path))
        elif isinstance(value, dict) and value:
            results.extend(untracked_paths(value, path))
    return results


def add_to_schema(schema: dict, rel_path: str):
    root_key = next((k for k in schema if k.rstrip("+") == "root"), None)
    if root_key is None:
        root_key = "root+"
        schema[root_key] = {}
    node = schema[root_key]

    if rel_path == "":
        if not root_key.endswith("+"):
            schema["root+"] = schema.pop(root_key)
        return

    parts = rel_path.split("/")
    for i, part in enumerate(parts):
        is_last = i == len(parts) - 1
        existing = next((k for k in (node or {}) if k.rstrip("+") == part), None)
        target_key = f"{part}+" if is_last else (existing or part)
        if existing and existing != target_key:
            node[target_key] = node.pop(existing)
        elif target_key not in (node or {}):
            node[target_key] = {}
        node = node[target_key]


# ── Path helpers ─────────────────────────────────────────────────────────────

def doc_path(rel_path: str) -> Path:
    fn = get_doc_filename()
    if rel_path == "":
        return DOCS_ROOT / fn
    return DOCS_ROOT / rel_path / fn


def symlink_path(repo: Path, rel_path: str) -> Path:
    fn = get_doc_filename()
    if rel_path == "":
        return repo / fn
    return repo / rel_path / fn


def schema_paths(schema: dict) -> list[str]:
    return [p for p, _ in walk_schema(schema)]


def best_schema_match(file_path: str, paths: list[str]) -> Optional[str]:
    best = None
    best_len = -1
    for sp in paths:
        if sp == "":
            if "/" not in file_path and best_len < 0:
                best = sp
                best_len = 0
        elif file_path == sp or file_path.startswith(sp + "/"):
            if len(sp) > best_len:
                best = sp
                best_len = len(sp)
    return best


def ancestor_paths(rel_path: str, all_paths: list[str]) -> list[str]:
    if rel_path == "":
        return []
    parts = rel_path.split("/")
    ancestors = []
    for i in range(len(parts)):
        candidate = "/".join(parts[:i]) if i > 0 else ""
        if candidate in all_paths and candidate != rel_path:
            ancestors.append(candidate)
    return ancestors


# ── Git helpers ───────────────────────────────────────────────────────────────

def _git(repo: Path, *args) -> list[str]:
    result = subprocess.run(
        ["git", "-C", str(repo)] + list(args),
        capture_output=True, text=True
    )
    return [f for f in result.stdout.strip().split("\n") if f]


def git_staged_files(repo: Path) -> list[str]:
    return _git(repo, "diff", "--name-only", "--cached")


def git_unstaged_files(repo: Path) -> list[str]:
    return _git(repo, "diff", "--name-only")


def git_all_changed_files(repo: Path) -> list[str]:
    return list(set(git_staged_files(repo) + git_unstaged_files(repo)))


def git_ref_files(repo: Path, ref: str) -> list[str]:
    return _git(repo, "diff", "--name-only", ref)


def git_head_hash(repo: Path) -> Optional[str]:
    result = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "--short", "HEAD"],
        capture_output=True, text=True
    )
    h = result.stdout.strip()
    return h if h else None


def git_log_range(repo: Path, from_commit: str, path: str = "") -> list[str]:
    """Return files changed between from_commit and HEAD under path (target repo)."""
    cmd = ["git", "-C", str(repo), "diff", "--name-only", f"{from_commit}..HEAD"]
    if path:
        cmd += ["--", path]
    result = subprocess.run(cmd, capture_output=True, text=True)
    return [f for f in result.stdout.strip().split("\n") if f]


def commit_is_ancestor(repo: Path, commit: str) -> bool:
    """Return True if commit exists and is an ancestor of HEAD."""
    result = subprocess.run(
        ["git", "-C", str(repo), "merge-base", "--is-ancestor", commit, "HEAD"],
        capture_output=True,
    )
    return result.returncode == 0


# ── Metadata footer ──────────────────────────────────────────────────────────

_HEADER_MARKER = "<!-- agent-wiki"
_HEADER_END = "-->"


def get_wiki_commit_id() -> Optional[str]:
    result = subprocess.run(
        ["git", "-C", str(WIKI_ROOT), "rev-parse", "--short", "HEAD"],
        capture_output=True, text=True,
    )
    h = result.stdout.strip()
    return h if h else None


def strip_wiki_banner(content: str) -> str:
    """Strip legacy > **WIKI MANAGED** banner (kept for migration compatibility)."""
    if not content.lstrip().startswith("> **WIKI MANAGED**"):
        return content
    idx = content.find("---\n\n")
    if idx != -1:
        return content[idx + len("---\n\n"):]
    return content.split("\n", 1)[-1].lstrip("\n")


def strip_metadata_footer(content: str) -> str:
    """Strip legacy <!-- agent-wiki-meta --> footer (kept for migration compatibility)."""
    marker = "<!-- agent-wiki-meta"
    idx = content.find("\n" + marker)
    if idx != -1:
        return content[:idx]
    if content.startswith(marker):
        end = content.find(_HEADER_END)
        if end != -1:
            return content[end + len(_HEADER_END):].lstrip("\n")
    return content


def strip_wiki_header(content: str) -> str:
    """Strip the unified <!-- agent-wiki ... --> header block."""
    if _HEADER_MARKER not in content:
        # Fall back to stripping legacy formats
        content = strip_wiki_banner(content)
        content = strip_metadata_footer(content)
        return content
    start = content.find(_HEADER_MARKER)
    end = content.find(_HEADER_END, start)
    if end == -1:
        return content
    stripped = content[end + len(_HEADER_END):].lstrip("\n")
    return stripped


def read_metadata_footer(doc: Path) -> dict:
    """Return key→value metadata from the agent-wiki header block (or legacy footer)."""
    if not doc.exists():
        return {}
    content = doc.read_text()
    # New unified header
    start = content.find(_HEADER_MARKER)
    if start != -1:
        end = content.find(_HEADER_END, start)
        if end != -1:
            block = content[start + len(_HEADER_MARKER):end]
            result = {}
            for line in block.strip().splitlines():
                if ":" in line:
                    k, _, v = line.partition(":")
                    result[k.strip()] = v.strip()
            return result
    # Legacy footer fallback
    legacy = "<!-- agent-wiki-meta"
    start = content.find(legacy)
    if start == -1:
        return {}
    end = content.find(_HEADER_END, start)
    if end == -1:
        return {}
    block = content[start + len(legacy):end]
    result = {}
    for line in block.strip().splitlines():
        if ":" in line:
            k, _, v = line.partition(":")
            result[k.strip()] = v.strip()
    return result


def write_metadata_footer(doc: Path, rel_path: str, touched_by: str,
                          source_commit: Optional[str] = None):
    from datetime import date
    content = doc.read_text() if doc.exists() else ""
    # Preserve existing SourceCommitID if not explicitly provided
    if source_commit is None:
        existing = read_metadata_footer(doc)
        source_commit = existing.get("SourceCommitID")
    # Strip both new header and legacy formats
    content = strip_wiki_header(content)
    fn = get_doc_filename()
    location = f"{rel_path}/{fn}" if rel_path else fn
    wiki_commit = get_wiki_commit_id()
    lines = [
        _HEADER_MARKER,
        "Check .agent-wiki/flags.json before starting doc work.",
        "LLM Guide: .agent-wiki/agents/llm.md",
        "Wiki Index: .agent-wiki/AGENT-INDEX.md",
        "",
        f"Location: {location}",
        f"LastTouchedBy: {touched_by}",
        f"ChangeDate: {date.today().isoformat()}",
    ]
    if wiki_commit:
        lines.append(f"WikiCommitID: {wiki_commit}")
    if source_commit:
        lines.append(f"SourceCommitID: {source_commit}")
    lines.append(_HEADER_END)
    doc.write_text("\n".join(lines) + "\n\n" + content.lstrip("\n"))


# ── Scope resolution ─────────────────────────────────────────────────────────

def resolve_scope(scope: Optional[str], repo: Path) -> tuple[list[str], list[str]]:
    schema = load_schema()
    s_paths = schema_paths(schema)

    if scope is None:
        entries = load_drift_log()
        files = list({e["path"] for e in entries})
        docs = list({e["wiki_doc"] for e in entries})
        return files, docs

    if scope == "staged":
        files = git_staged_files(repo)
    elif scope == "diff":
        files = git_all_changed_files(repo)
    elif Path(repo / scope).is_dir():
        files = [
            str(f.relative_to(repo))
            for f in (repo / scope).rglob("*")
            if f.is_file() and ".git" not in f.parts
        ]
    elif Path(repo / scope).is_file():
        files = [scope]
    else:
        files = git_ref_files(repo, scope)

    docs = []
    for f in files:
        match = best_schema_match(f, s_paths)
        if match is not None and match not in docs:
            docs.append(match)

    return files, docs


# ── Logging ──────────────────────────────────────────────────────────────────

def now_ts() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def append_log(log_file: Path, entry: dict):
    log_file.parent.mkdir(parents=True, exist_ok=True)
    with open(log_file, "a") as f:
        f.write(json.dumps(entry) + "\n")


def load_drift_log() -> list[dict]:
    if not DRIFT_LOG.exists():
        return []
    entries = []
    for line in DRIFT_LOG.read_text().strip().split("\n"):
        line = line.strip()
        if line:
            entries.append(json.loads(line))
    return entries


def clear_drift_log():
    if DRIFT_LOG.exists():
        DRIFT_LOG.write_text("")


def clear_drift_log_for(processed_rel_paths: list[str]):
    """Remove drift entries whose wiki_doc maps to one of the processed rel_paths."""
    if not DRIFT_LOG.exists():
        return
    def _display(rp: str) -> str:
        fn = get_doc_filename()
        return f"docs/{rp}/{fn}" if rp else f"docs/{fn}"
    keep_docs = {_display(rp) for rp in processed_rel_paths}
    remaining = [e for e in load_drift_log() if e.get("wiki_doc") not in keep_docs]
    DRIFT_LOG.write_text("".join(json.dumps(e) + "\n" for e in remaining))


def load_new_entry_log() -> list[dict]:
    if not NEW_ENTRY_LOG.exists():
        return []
    entries = []
    for line in NEW_ENTRY_LOG.read_text().strip().split("\n"):
        line = line.strip()
        if line:
            entries.append(json.loads(line))
    return entries


def clear_new_entry_log(processed_rel_paths: Optional[list[str]] = None):
    """Remove processed entries. Pass None to clear all."""
    if not NEW_ENTRY_LOG.exists():
        return
    if processed_rel_paths is None:
        NEW_ENTRY_LOG.write_text("")
        return
    remaining = [e for e in load_new_entry_log() if e.get("rel_path") not in processed_rel_paths]
    NEW_ENTRY_LOG.write_text("".join(json.dumps(e) + "\n" for e in remaining))


# ── Conflict log ──────────────────────────────────────────────────────────────

def load_conflict_log() -> list[dict]:
    if not CONFLICT_LOG.exists():
        return []
    entries = []
    for line in CONFLICT_LOG.read_text().strip().split("\n"):
        line = line.strip()
        if line:
            entries.append(json.loads(line))
    return entries


def clear_conflict_log_for(resolved_rel_paths: Optional[list[str]] = None):
    """Remove resolved entries. Pass None to clear all."""
    if not CONFLICT_LOG.exists():
        return
    if resolved_rel_paths is None:
        CONFLICT_LOG.write_text("")
        return
    remaining = [e for e in load_conflict_log() if e.get("rel_path") not in resolved_rel_paths]
    CONFLICT_LOG.write_text("".join(json.dumps(e) + "\n" for e in remaining))


# ── Flags ─────────────────────────────────────────────────────────────────────

def load_flags() -> dict:
    if not FLAGS_FILE.exists():
        return {}
    return json.loads(FLAGS_FILE.read_text())


def set_flag(key: str, value=True):
    flags = load_flags()
    flags[key] = value
    flags["last_updated"] = now_ts()
    FLAGS_FILE.parent.mkdir(parents=True, exist_ok=True)
    FLAGS_FILE.write_text(json.dumps(flags, indent=2) + "\n")


def clear_flag(*keys: str):
    flags = load_flags()
    changed = False
    for key in keys:
        if key in flags:
            del flags[key]
            changed = True
    if changed:
        flags["last_updated"] = now_ts()
        FLAGS_FILE.write_text(json.dumps(flags, indent=2) + "\n")
