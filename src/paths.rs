use std::path::{Component, Path, PathBuf};

use crate::root::WikiCtx;

/// Absolute path to the wiki doc for `rel_path` (may not exist yet).
pub fn doc_path(ctx: &WikiCtx, rel_path: &str, doc_filename: &str) -> PathBuf {
    if rel_path.is_empty() {
        ctx.docs_root().join(doc_filename)
    } else {
        ctx.docs_root().join(rel_path).join(doc_filename)
    }
}

/// Absolute path to the symlink in the target repo for `rel_path`.
pub fn symlink_path(repo_root: &Path, rel_path: &str, doc_filename: &str) -> PathBuf {
    if rel_path.is_empty() {
        repo_root.join(doc_filename)
    } else {
        repo_root.join(rel_path).join(doc_filename)
    }
}

/// Display path used in logs and output: `"docs/src/CLAUDE.md"` or `"docs/CLAUDE.md"`.
pub fn display_doc(rel_path: &str, doc_filename: &str) -> String {
    if rel_path.is_empty() {
        format!("docs/{doc_filename}")
    } else {
        format!("docs/{rel_path}/{doc_filename}")
    }
}

/// Compute a relative path from `from_dir` to `target` (both absolute).
/// Equivalent to Python's `os.path.relpath(target, from_dir)`.
pub fn relpath(target: &Path, from_dir: &Path) -> PathBuf {
    let t_comps: Vec<Component> = target.components().collect();
    let f_comps: Vec<Component> = from_dir.components().collect();
    let common = t_comps
        .iter()
        .zip(f_comps.iter())
        .take_while(|(a, b)| a == b)
        .count();
    let mut result = PathBuf::new();
    for _ in common..f_comps.len() {
        result.push("..");
    }
    for c in &t_comps[common..] {
        result.push(c);
    }
    result
}
