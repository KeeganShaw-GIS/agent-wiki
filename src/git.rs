use std::path::Path;
use std::process::Command;

fn git(repo: &Path, args: &[&str]) -> Vec<String> {
    let Ok(out) = Command::new("git")
        .arg("-C")
        .arg(repo)
        .args(args)
        .output()
    else {
        return vec![];
    };
    String::from_utf8_lossy(&out.stdout)
        .split('\n')
        .filter(|s| !s.is_empty())
        .map(str::to_string)
        .collect()
}

pub fn head_hash(repo: &Path) -> Option<String> {
    let out = Command::new("git")
        .args(["-C", repo.to_str().unwrap_or("."), "rev-parse", "--short", "HEAD"])
        .output()
        .ok()?;
    let h = String::from_utf8_lossy(&out.stdout).trim().to_string();
    if h.is_empty() { None } else { Some(h) }
}

pub fn staged_files(repo: &Path) -> Vec<String> {
    git(repo, &["diff", "--name-only", "--cached"])
}

pub fn changed_files(repo: &Path) -> Vec<String> {
    let mut files = staged_files(repo);
    files.extend(git(repo, &["diff", "--name-only"]));
    files.sort();
    files.dedup();
    files
}

pub fn ref_files(repo: &Path, git_ref: &str) -> Vec<String> {
    git(repo, &["diff", "--name-only", git_ref])
}

/// Files changed between `from_commit..HEAD` under `scope_path`.
pub fn log_range(repo: &Path, from_commit: &str, scope_path: &str) -> Vec<String> {
    let range = format!("{from_commit}..HEAD");
    let mut args = vec!["diff", "--name-only", &range];
    let scope_str;
    if !scope_path.is_empty() {
        args.extend(["--", scope_path]);
        scope_str = scope_path.to_string();
        let _ = scope_str;
    }
    // Rebuild cleanly to avoid lifetime issues
    let mut cmd = Command::new("git");
    cmd.arg("-C").arg(repo).arg("diff").arg("--name-only").arg(&range);
    if !scope_path.is_empty() {
        cmd.arg("--").arg(scope_path);
    }
    let Ok(out) = cmd.output() else { return vec![]; };
    String::from_utf8_lossy(&out.stdout)
        .split('\n')
        .filter(|s| !s.is_empty())
        .map(str::to_string)
        .collect()
}

pub fn is_ancestor(repo: &Path, commit: &str) -> bool {
    Command::new("git")
        .args(["-C", repo.to_str().unwrap_or("."), "merge-base", "--is-ancestor", commit, "HEAD"])
        .output()
        .map(|o| o.status.success())
        .unwrap_or(false)
}

pub fn skip_worktree(repo: &Path, rel_file: &str) {
    let _ = Command::new("git")
        .args(["-C", repo.to_str().unwrap_or("."), "update-index", "--skip-worktree", rel_file])
        .output();
}

pub fn no_skip_worktree(repo: &Path, rel_file: &str) {
    let _ = Command::new("git")
        .args(["-C", repo.to_str().unwrap_or("."), "update-index", "--no-skip-worktree", rel_file])
        .output();
}

pub fn init(dir: &Path) -> bool {
    Command::new("git")
        .arg("init")
        .arg(dir)
        .output()
        .map(|o| o.status.success())
        .unwrap_or(false)
}

pub fn add_remote(repo: &Path, url: &str) -> bool {
    Command::new("git")
        .args(["-C", repo.to_str().unwrap_or("."), "remote", "add", "origin", url])
        .output()
        .map(|o| o.status.success())
        .unwrap_or(false)
}
