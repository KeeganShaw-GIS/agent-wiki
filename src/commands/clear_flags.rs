use anyhow::Result;

use crate::{
    config,
    git,
    logs,
    metadata,
    paths::doc_path,
    root::WikiCtx,
};

pub fn run(ctx: &WikiCtx, flags: &[String]) -> Result<()> {
    let clearing_drift = flags.is_empty() || flags.iter().any(|f| f == "drift_detected");
    if clearing_drift && !logs::load_drift(&ctx.wiki_root).is_empty() {
        stamp_drift_checked(ctx)?;
    }

    // Auto-clear flags whose backing log is now empty
    let mut flags_state = logs::load_flags(&ctx.wiki_root);
    let auto_keys = ["multiple_versions", "drift_detected", "new_entry"];
    for key in auto_keys {
        if !flags_state.contains_key(key) {
            continue;
        }
        let empty = match key {
            "multiple_versions" => logs::load_conflicts(&ctx.wiki_root).is_empty(),
            "drift_detected" => logs::load_drift(&ctx.wiki_root).is_empty(),
            "new_entry" => logs::load_new_entries(&ctx.wiki_root).is_empty(),
            _ => false,
        };
        if empty {
            logs::clear_flags(&ctx.wiki_root, &[key]);
            flags_state.remove(key);
            println!("  [auto-cleared]  {key}  (backing log is empty)");
        }
    }

    if flags_state.is_empty() {
        println!("No flags set.");
        return Ok(());
    }

    if flags.is_empty() {
        let keys: Vec<String> = flags_state
            .keys()
            .filter(|k| *k != "last_updated")
            .cloned()
            .collect();
        let refs: Vec<&str> = keys.iter().map(String::as_str).collect();
        logs::clear_flags(&ctx.wiki_root, &refs);
        for k in &keys {
            println!("  [cleared]  {k}");
        }
    } else {
        let refs: Vec<&str> = flags.iter().map(String::as_str).collect();
        logs::clear_flags(&ctx.wiki_root, &refs);
        for f in flags {
            println!("  [cleared]  {f}");
        }
    }

    println!(
        "  flags.json updated: {}",
        ctx.wiki_root.join("logs").join("flags.json").display()
    );
    Ok(())
}

fn stamp_drift_checked(ctx: &WikiCtx) -> Result<()> {
    let cfg = config::load(&ctx.wiki_root)?;
    let repo = ctx.repo_root();
    let Some(head) = git::head_hash(repo) else {
        return Ok(());
    };
    for entry in logs::load_drift(&ctx.wiki_root) {
        let dp = doc_path(ctx, &entry.rel_path, &cfg.doc_filename);
        if dp.exists() {
            metadata::write_header(
                &dp,
                &entry.rel_path,
                "agent-wiki clear-flags",
                &cfg.doc_filename,
                git::head_hash(&ctx.wiki_root).as_deref(),
                Some(&head),
            )?;
            println!("  [stamped]  {}  SourceCommitID={head}", entry.wiki_doc);
        }
    }
    Ok(())
}
