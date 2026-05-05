use anyhow::Result;

use crate::{
    config,
    git,
    logs::{self, DriftEntry},
    metadata,
    paths::{display_doc, doc_path},
    root::WikiCtx,
    schema::{self, ancestor_paths},
};

pub fn run(ctx: &WikiCtx, staged_only: bool) -> Result<()> {
    let cfg = config::load(&ctx.wiki_root)?;
    let sch = schema::load(&ctx.wiki_root)?;
    let managed = schema::walk(&sch, "");
    let repo = ctx.repo_root();

    let Some(head) = git::head_hash(repo) else {
        return Ok(());
    };

    let staged = if staged_only {
        Some(git::staged_files(repo).into_iter().collect::<std::collections::HashSet<_>>())
    } else {
        None
    };

    let mut existing: std::collections::HashMap<String, DriftEntry> = logs::load_drift(&ctx.wiki_root)
        .into_iter()
        .map(|e| (e.rel_path.clone(), e))
        .collect();

    let mut logged = 0;

    for rel_path in &managed {
        let dp = doc_path(ctx, rel_path, &cfg.doc_filename);
        if !dp.exists() {
            continue;
        }

        let footer = metadata::read_header(&dp);
        let Some(from_commit) = footer.get("SourceCommitID") else {
            continue;
        };
        if !git::is_ancestor(repo, from_commit) {
            continue;
        }

        let mut changed = git::log_range(repo, from_commit, rel_path);
        if let Some(staged_set) = &staged {
            changed.retain(|f| staged_set.contains(f));
        }

        if changed.is_empty() {
            existing.remove(rel_path.as_str());
            continue;
        }

        let parents = ancestor_paths(rel_path, &managed);
        let entry = DriftEntry {
            ts: chrono::Utc::now().format("%Y-%m-%dT%H:%M:%SZ").to_string(),
            trigger: if staged_only { "pre-commit" } else { "manual" }.into(),
            rel_path: rel_path.clone(),
            wiki_doc: display_doc(rel_path, &cfg.doc_filename),
            from_commit: from_commit.clone(),
            to_commit: head.clone(),
            changed_files: changed,
            parent_paths: parents,
        };
        existing.insert(rel_path.clone(), entry);
        logged += 1;
    }

    let entries: Vec<DriftEntry> = existing.into_values().collect();
    if entries.is_empty() {
        logs::clear_drift(&ctx.wiki_root);
    } else {
        logs::write_drift(&ctx.wiki_root, &entries);
        logs::set_flag(&ctx.wiki_root, "drift_detected", serde_json::Value::Bool(true));
        println!("  [drift] {logged} doc(s) with drift logged");
    }

    Ok(())
}
