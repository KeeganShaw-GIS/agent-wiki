use anyhow::Result;
use std::path::Path;

use crate::{
    config,
    git,
    logs,
    paths::doc_path,
    root::WikiCtx,
    schema::{self, ancestor_paths, best_match},
};

const PLACEHOLDER: &str = "Not yet populated";

pub fn run(ctx: &WikiCtx, scope: Option<&str>) -> Result<()> {
    let cfg = config::load(&ctx.wiki_root)?;
    let sch = schema::load(&ctx.wiki_root)?;
    let managed = schema::walk(&sch, "");
    let repo = ctx.repo_root();

    let (source_files, mut wiki_rel_paths) = resolve_scope(ctx, scope, repo, &managed)?;

    let mut new_entry_paths: std::collections::HashSet<String> = std::collections::HashSet::new();
    if scope.is_none() {
        for e in logs::load_new_entries(&ctx.wiki_root) {
            if !wiki_rel_paths.contains(&e.rel_path) {
                wiki_rel_paths.push(e.rel_path.clone());
            }
            new_entry_paths.insert(e.rel_path);
        }
    }

    if wiki_rel_paths.is_empty() && new_entry_paths.is_empty() {
        println!("Nothing pending — drift log and new-entry log are both empty.");
        return Ok(());
    }

    // Expand to include ancestors
    let mut all_rel_paths = wiki_rel_paths.clone();
    for rp in &wiki_rel_paths {
        if new_entry_paths.contains(rp) {
            continue;
        }
        for anc in ancestor_paths(rp, &managed) {
            if !all_rel_paths.contains(&anc) {
                all_rel_paths.push(anc);
            }
        }
    }

    let scope_label = describe_scope(ctx, scope, &new_entry_paths, &wiki_rel_paths);
    println!("Status — pending docs");
    println!("  scope:  {scope_label}\n");

    let fn_ = &cfg.doc_filename;
    for rel_path in &all_rel_paths {
        let dp = doc_path(ctx, rel_path, fn_);
        let display = if rel_path.is_empty() {
            format!("docs/{fn_}")
        } else {
            format!("docs/{rel_path}/{fn_}")
        };
        let kind = if new_entry_paths.contains(rel_path) {
            "new-file"
        } else if scope.is_none() {
            "drift"
        } else {
            "manual"
        };
        let is_new = is_placeholder(&dp);
        let mut scoped: Vec<&str> = source_files
            .iter()
            .filter(|f| best_match(f, &[rel_path.clone()]).is_some())
            .map(String::as_str)
            .collect();
        if scoped.is_empty() && (is_new || new_entry_paths.contains(rel_path)) {
            scoped = scan_dir_files(repo, rel_path, fn_)
                .iter()
                .map(|_| "")
                .collect::<Vec<_>>();
            // Re-scan with owned strings
            let owned = scan_dir_files(repo, rel_path, fn_);
            println!(
                "  {:<50}  [{kind}]  {} source file(s)",
                display,
                owned.len()
            );
        } else {
            println!("  {:<50}  [{kind}]  {} source file(s)", display, scoped.len());
        }

        let ancestors = ancestor_paths(rel_path, &managed);
        let existing_ancs: Vec<String> = ancestors
            .iter()
            .filter(|anc| {
                let adp = doc_path(ctx, anc, fn_);
                adp.exists() && !is_placeholder(&adp)
            })
            .map(|anc| {
                if anc.is_empty() {
                    format!("docs/{fn_}")
                } else {
                    format!("docs/{anc}/{fn_}")
                }
            })
            .collect();
        if !existing_ancs.is_empty() {
            println!("    context: {}", existing_ancs.join(", "));
        }
    }

    println!("\n{} doc(s) pending.", all_rel_paths.len());
    Ok(())
}

fn resolve_scope(
    ctx: &WikiCtx,
    scope: Option<&str>,
    repo: &Path,
    managed: &[String],
) -> Result<(Vec<String>, Vec<String>)> {
    let Some(scope) = scope else {
        let drift = logs::load_drift(&ctx.wiki_root);
        let files: Vec<String> = drift.iter().flat_map(|e| e.changed_files.clone()).collect();
        let docs: Vec<String> = drift.iter().map(|e| e.rel_path.clone()).collect();
        return Ok((files, docs));
    };

    let files = match scope {
        "staged" => git::staged_files(repo),
        "diff" => git::changed_files(repo),
        s if repo.join(s).is_dir() => {
            walkdir::WalkDir::new(repo.join(s))
                .into_iter()
                .filter_map(|e| e.ok())
                .filter(|e| e.file_type().is_file())
                .filter(|e| !e.path().components().any(|c| c.as_os_str() == ".git"))
                .map(|e| e.path().strip_prefix(repo).unwrap().to_string_lossy().into_owned())
                .collect()
        }
        s if repo.join(s).is_file() => vec![s.to_string()],
        s => git::ref_files(repo, s),
    };

    let docs: Vec<String> = files
        .iter()
        .filter_map(|f| crate::schema::best_match(f, managed))
        .collect::<std::collections::HashSet<_>>()
        .into_iter()
        .collect();

    Ok((files, docs))
}

fn describe_scope(
    ctx: &WikiCtx,
    scope: Option<&str>,
    new_entry_paths: &std::collections::HashSet<String>,
    wiki_rel_paths: &[String],
) -> String {
    let Some(scope) = scope else {
        let has_drift = !wiki_rel_paths.iter().all(|p| new_entry_paths.contains(p));
        return match (has_drift, !new_entry_paths.is_empty()) {
            (true, true) => "drift + new-entries".into(),
            (false, true) => "new-entries".into(),
            _ => "drift-log".into(),
        };
    };
    let repo = ctx.repo_root();
    match scope {
        "staged" => "git staged".into(),
        "diff" => "git diff".into(),
        s if repo.join(s).is_dir() => format!("folder  ({s})"),
        s if repo.join(s).is_file() => format!("file  ({s})"),
        s => format!("git ref  ({s})"),
    }
}

fn is_placeholder(path: &Path) -> bool {
    path.exists()
        && std::fs::read_to_string(path)
            .map(|c| c.contains(PLACEHOLDER))
            .unwrap_or(false)
}

fn scan_dir_files(repo: &Path, rel_path: &str, doc_filename: &str) -> Vec<String> {
    let target = if rel_path.is_empty() {
        repo.to_path_buf()
    } else {
        repo.join(rel_path)
    };
    if !target.is_dir() {
        return vec![];
    }
    walkdir::WalkDir::new(&target)
        .into_iter()
        .filter_map(|e| e.ok())
        .filter(|e| {
            e.file_type().is_file()
                && e.file_name().to_string_lossy() != doc_filename
                && !e.path().components().any(|c| c.as_os_str() == ".git")
        })
        .map(|e| e.path().strip_prefix(repo).unwrap().to_string_lossy().into_owned())
        .collect()
}
