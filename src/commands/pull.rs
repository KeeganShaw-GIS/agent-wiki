use anyhow::Result;
use std::fs;

use crate::{
    config,
    git,
    logs::{self, ConflictEntry},
    metadata,
    paths::{doc_path, symlink_path},
    root::WikiCtx,
    schema::{self, untracked},
};

pub fn run(ctx: &WikiCtx, strategy: &str) -> Result<()> {
    let (found, paths) = run_detect_and_integrate(ctx, strategy, false)?;
    if found > 0 {
        println!("\n  Integrated {found} file(s) and updated schema.yaml.");
    }
    if !paths.is_empty() {
        println!("  Absorbed docs (review recommended):");
        for p in &paths {
            println!("    {p}");
        }
    }
    Ok(())
}

/// Scan the target repo for unmanaged doc files and absorb them.
/// Returns `(absorbed_count, absorbed_paths)`.
pub fn run_detect_and_integrate(
    ctx: &WikiCtx,
    strategy: &str,
    quiet: bool,
) -> Result<(usize, Vec<String>)> {
    let cfg = config::load(&ctx.wiki_root)?;
    let fn_ = &cfg.doc_filename;
    let mut sch = schema::load(&ctx.wiki_root)?;
    let repo = ctx.repo_root();
    let managed_paths = schema::walk(&sch, "");
    let skipped = untracked(&sch, "");
    let existing_conflicts: Vec<String> = logs::load_conflicts(&ctx.wiki_root)
        .into_iter()
        .map(|e| e.rel_path)
        .collect();

    let managed_links: std::collections::HashSet<String> = managed_paths
        .iter()
        .map(|rp| {
            symlink_path(repo, rp, fn_)
                .strip_prefix(repo)
                .unwrap()
                .to_string_lossy()
                .into_owned()
        })
        .collect();

    let local_edits = ctx.wiki_root.join("logs").join("local-edits");
    let mut found = 0;
    let mut conflicts = 0;
    let mut absorbed_paths = Vec::new();
    let mut schema_changed = false;

    for entry in walkdir::WalkDir::new(repo)
        .into_iter()
        .filter_map(|e| e.ok())
        .filter(|e| e.file_name().to_string_lossy() == *fn_)
    {
        let file = entry.path();
        if file.components().any(|c| {
            let s = c.as_os_str().to_string_lossy();
            s == ".git" || s == ".agent-wiki"
        }) {
            continue;
        }

        let rel_file = file.strip_prefix(repo).unwrap().to_string_lossy().into_owned();
        let rel_path = file
            .parent()
            .and_then(|p| p.strip_prefix(repo).ok())
            .map(|p| if p == std::path::Path::new("") { "".to_string() } else { p.to_string_lossy().into_owned() })
            .unwrap_or_default();

        // Orphan symlink: managed-banner, not in schema
        if file.is_symlink() {
            if !managed_links.contains(&rel_file) {
                if let Ok(target) = file.read_link() {
                    if let Ok(content) = fs::read_to_string(&target) {
                        if metadata::has_header(&content) {
                            fs::remove_file(file)?;
                            fs::write(file, metadata::strip_header(&content))?;
                            if !quiet {
                                println!("  [orphan-ejected] {rel_file}");
                            }
                        }
                    }
                }
            }
            continue;
        }

        if skipped.contains(&rel_path) {
            continue;
        }

        let wiki_doc = doc_path(ctx, &rel_path, fn_);

        if wiki_doc.exists() {
            match strategy {
                "skip" => {
                    if !existing_conflicts.contains(&rel_path) {
                        logs::append_conflict(
                            &ctx.wiki_root,
                            ConflictEntry {
                                ts: chrono::Utc::now().format("%Y-%m-%dT%H:%M:%SZ").to_string(),
                                rel_path: rel_path.clone(),
                                repo_file: rel_file.clone(),
                                wiki_doc: wiki_doc.to_string_lossy().into_owned(),
                                wiki_backup: None,
                                resolution: None,
                            },
                        );
                        logs::set_flag(&ctx.wiki_root, "multiple_versions", serde_json::Value::Bool(true));
                    }
                    if !quiet {
                        println!("  [conflict] {rel_path} — run `pull --strategy wiki` or `pull --strategy repo` to resolve");
                    }
                    conflicts += 1;
                    continue;
                }
                "wiki" => {
                    fs::remove_file(file)?;
                    let rel = crate::paths::relpath(&wiki_doc, file.parent().unwrap());
                    std::os::unix::fs::symlink(&rel, file)?;
                    if !quiet {
                        println!("  [wiki-wins] {rel_file}");
                    }
                    logs::clear_conflicts_for(&ctx.wiki_root, &[rel_path.as_str()]);
                    if logs::load_conflicts(&ctx.wiki_root).is_empty() {
                        logs::clear_flags(&ctx.wiki_root, &["multiple_versions"]);
                    }
                    absorbed_paths.push(if rel_path.is_empty() { "(root)".into() } else { rel_path.clone() });
                    found += 1;
                    continue;
                }
                _ => {
                    // strategy == "repo": backup wiki, repo wins
                    fs::create_dir_all(&local_edits)?;
                    let backup_name = (if rel_path.is_empty() { "root".to_string() } else { rel_path.replace('/', "-") }) + ".md";
                    let backup = local_edits.join(&backup_name);
                    fs::copy(&wiki_doc, &backup)?;
                    logs::append_conflict(
                        &ctx.wiki_root,
                        ConflictEntry {
                            ts: chrono::Utc::now().format("%Y-%m-%dT%H:%M:%SZ").to_string(),
                            rel_path: rel_path.clone(),
                            repo_file: rel_file.clone(),
                            wiki_doc: wiki_doc.to_string_lossy().into_owned(),
                            wiki_backup: Some(backup.to_string_lossy().into_owned()),
                            resolution: Some("repo-wins".into()),
                        },
                    );
                    logs::set_flag(&ctx.wiki_root, "multiple_versions", serde_json::Value::Bool(true));
                    if !quiet {
                        println!("  [repo-wins] {rel_path} — old wiki backed up to logs/local-edits/{backup_name}");
                    }
                }
            }
        }

        // Strip any header before absorbing
        let raw = fs::read_to_string(file)?;
        if metadata::has_header(&raw) {
            fs::write(file, metadata::strip_header(&raw))?;
        }

        absorb_file(file, &wiki_doc)?;
        let head = git::head_hash(repo);
        metadata::write_header(
            &wiki_doc, &rel_path, "agent-wiki pull", fn_,
            git::head_hash(&ctx.wiki_root).as_deref(),
            head.as_deref(),
        )?;
        schema::add_path(&mut sch, &rel_path);
        schema_changed = true;
        absorbed_paths.push(if rel_path.is_empty() { "(root)".into() } else { rel_path });
        found += 1;
    }

    if schema_changed {
        let fn_ = &cfg.doc_filename;
        schema::save(&ctx.wiki_root, &sch, fn_)?;
    }

    if !quiet {
        if conflicts > 0 {
            println!("\n  {conflicts} conflict(s) flagged.");
        }
        if found == 0 && conflicts == 0 {
            println!("  No unmanaged {} files found.", cfg.doc_filename);
        }
    }

    Ok((found, absorbed_paths))
}

fn absorb_file(src: &std::path::Path, dest: &std::path::Path) -> Result<()> {
    dest.parent().map(fs::create_dir_all).transpose()?;
    fs::copy(src, dest)?;
    fs::remove_file(src)?;
    let rel = crate::paths::relpath(dest, src.parent().unwrap());
    std::os::unix::fs::symlink(&rel, src)?;
    Ok(())
}
