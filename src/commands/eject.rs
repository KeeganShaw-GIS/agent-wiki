use anyhow::{bail, Result};
use std::fs;

use crate::{
    config,
    git,
    logs,
    metadata,
    paths::{doc_path, symlink_path},
    root::WikiCtx,
    schema,
};

pub fn run(ctx: &WikiCtx, scope: Option<&str>, purge: bool) -> Result<()> {
    let cfg = config::load(&ctx.wiki_root)?;
    let sch = schema::load(&ctx.wiki_root)?;
    let mut managed = schema::walk(&sch, "");

    if let Some(s) = scope {
        if !managed.contains(&s.to_string()) {
            bail!(
                "'{}' is not a managed doc path.\nManaged paths: {}",
                s,
                managed.join(", ")
            );
        }
        managed.retain(|p| p == s);
    }

    let fn_ = &cfg.doc_filename;
    let repo = ctx.repo_root();
    let local_edits = ctx.wiki_root.join("logs").join("local-edits");
    let mut ejected = Vec::new();

    for rel_path in &managed {
        let link = symlink_path(repo, rel_path, fn_);
        let wiki_doc = doc_path(ctx, rel_path, fn_);

        if !link.is_symlink() {
            println!(
                "  [skip]     {}  (not a symlink)",
                link.strip_prefix(repo).unwrap_or(&link).display()
            );
            continue;
        }
        if !wiki_doc.exists() {
            println!(
                "  [skip]     {}  (wiki doc missing)",
                display_doc(rel_path, fn_)
            );
            continue;
        }

        // Scoped eject backs up to logs/local-edits/
        if scope.is_some() {
            fs::create_dir_all(&local_edits)?;
            let name = (if rel_path.is_empty() { "root" } else { rel_path }).replace('/', "-") + ".md";
            fs::copy(&wiki_doc, local_edits.join(&name))?;
        }

        let content = metadata::strip_header(&fs::read_to_string(&wiki_doc)?);
        fs::remove_file(&link)?;
        fs::write(&link, content)?;
        git::no_skip_worktree(repo, &link.strip_prefix(repo).unwrap().to_string_lossy());
        ejected.push(rel_path.clone());
        println!(
            "  [ejected]  {}",
            link.strip_prefix(repo).unwrap_or(&link).display()
        );
    }

    let all_paths: Vec<&str> = managed.iter().map(String::as_str).collect();
    logs::clear_conflicts_for(&ctx.wiki_root, &all_paths);
    if logs::load_conflicts(&ctx.wiki_root).is_empty() {
        logs::clear_flags(&ctx.wiki_root, &["multiple_versions"]);
    }

    if ejected.is_empty() {
        println!("Nothing ejected.");
    } else {
        println!(
            "\n{} file(s) ejected. Wiki docs in .agent-wiki/docs/ are untouched.",
            ejected.len()
        );
        println!("To stop managing these paths, remove them from schema.yaml.");
    }

    if scope.is_none() {
        remove_wiki_integration(ctx, purge)?;
    }

    Ok(())
}

fn display_doc(rel_path: &str, fn_: &str) -> String {
    if rel_path.is_empty() {
        format!("docs/{fn_}")
    } else {
        format!("docs/{rel_path}/{fn_}")
    }
}

fn remove_wiki_integration(ctx: &WikiCtx, purge: bool) -> Result<()> {
    let repo = ctx.repo_root();

    // Back up git hooks owned by agent-wiki
    for hook_name in ["pre-commit", "post-checkout"] {
        let hook = repo.join(".git").join("hooks").join(hook_name);
        if hook.exists() {
            let content = fs::read_to_string(&hook).unwrap_or_default();
            if content.contains("agent-wiki") {
                let bak = hook.with_extension("agent-wiki.bak");
                fs::rename(&hook, &bak)?;
                println!("  [backup]   .git/hooks/{hook_name} → {}", bak.file_name().unwrap_or_default().to_string_lossy());
            }
        }
    }

    if purge {
        // Remove .agent-wiki/ entirely — docs are in git history
        if ctx.wiki_root.exists() {
            fs::remove_dir_all(&ctx.wiki_root)?;
            println!("  [removed]  .agent-wiki/  (docs preserved in git history)");
            println!("  Recover:   git clone <wiki-remote> .agent-wiki/ && agent-wiki push --verify");
        }
    } else {
        println!("\n  .agent-wiki/ preserved (docs remain in git history).");
        println!("  To fully remove: agent-wiki eject --purge");
    }

    Ok(())
}
