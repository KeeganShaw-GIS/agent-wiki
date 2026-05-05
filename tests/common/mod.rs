use std::fs;
use std::path::{Path, PathBuf};
use std::process::Command;

/// Create a minimal git repo with code files for testing.
pub fn make_target_repo(dir: &Path) -> PathBuf {
    let repo = dir.join("repo");
    fs::create_dir_all(&repo).unwrap();
    git(&repo, &["init"]);
    git(&repo, &["config", "user.email", "test@test.com"]);
    git(&repo, &["config", "user.name", "Test"]);

    fs::write(repo.join("README.md"), "# Test Repo\n").unwrap();
    fs::create_dir_all(repo.join("src")).unwrap();
    fs::write(repo.join("src/main.py"), "def main(): pass\n").unwrap();
    fs::create_dir_all(repo.join("frontend/components")).unwrap();
    fs::write(repo.join("frontend/app.ts"), "export default {};\n").unwrap();
    fs::write(repo.join("frontend/components/Button.tsx"), "export const Button = () => null;\n").unwrap();
    commit(&repo, "initial commit");
    repo
}

/// Run `agent-wiki init` (via library call) in `repo_root` with default options.
pub fn init_wiki(repo_root: &Path) -> agent_wiki::root::WikiCtx {
    agent_wiki::commands::init::run_in(
        repo_root.to_path_buf(),
        agent_wiki::commands::init::InitArgs {
            doc_filename: "CLAUDE.md".into(),
            no_detect_target_docs: true,
            no_hooks: true,
            wiki_remote: None,
        },
    )
    .expect("init failed")
}

/// Write a rich 4-path schema to `ctx.wiki_root/schema.yaml`.
pub fn write_rich_schema(ctx: &agent_wiki::root::WikiCtx) {
    fs::write(
        ctx.wiki_root.join("schema.yaml"),
        "root+:\n  src+:\n  frontend+:\n    components+:\n",
    )
    .unwrap();
}

pub fn git(repo: &Path, args: &[&str]) {
    let status = Command::new("git")
        .arg("-C")
        .arg(repo)
        .args(args)
        .status()
        .unwrap();
    assert!(status.success(), "git {:?} failed", args);
}

pub fn commit(repo: &Path, msg: &str) {
    git(repo, &["add", "."]);
    git(repo, &["commit", "-m", msg]);
}

pub fn is_valid_symlink(path: &Path) -> bool {
    path.is_symlink() && path.exists()
}

pub fn read_flags(wiki_root: &Path) -> serde_json::Value {
    let path = wiki_root.join("logs").join("flags.json");
    if !path.exists() {
        return serde_json::json!({});
    }
    serde_json::from_str(&fs::read_to_string(path).unwrap()).unwrap_or(serde_json::json!({}))
}

pub fn read_jsonl(wiki_root: &Path, name: &str) -> Vec<serde_json::Value> {
    let path = wiki_root.join("logs").join(name);
    if !path.exists() {
        return vec![];
    }
    fs::read_to_string(path)
        .unwrap()
        .lines()
        .filter(|l| !l.trim().is_empty())
        .filter_map(|l| serde_json::from_str(l).ok())
        .collect()
}
