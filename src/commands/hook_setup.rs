use anyhow::Result;
use std::fs;
#[cfg(unix)]
use std::os::unix::fs::PermissionsExt;

use crate::{
    config,
    git,
    paths::symlink_path,
    root::WikiCtx,
    schema,
};

const WRAPPER: &str = r#"#!/usr/bin/env bash
# agent-wiki wrapper — auto-generated. Do not edit.
exec agent-wiki "$@"
"#;

const PRE_COMMIT: &str = r#"#!/usr/bin/env bash
# agent-wiki: log changed source files to drift.jsonl before each commit.
ROOT=$(git rev-parse --show-toplevel)
"$ROOT/.agent-wiki/wiki" detect-drift --staged 2>/dev/null || true
exit 0
"#;

const POST_CHECKOUT: &str = r#"#!/usr/bin/env bash
# agent-wiki: create missing docs and symlinks after clone or branch switch.
ROOT=$(git rev-parse --show-toplevel)
"$ROOT/.agent-wiki/wiki" push 2>/dev/null || true
exit 0
"#;

pub fn run(ctx: &WikiCtx, pre_commit: bool, post_checkout: bool) -> Result<()> {
    let repo = ctx.repo_root();
    let git_dir = repo.join(".git");
    if !git_dir.exists() {
        return Err(anyhow::anyhow!("No .git directory found in {}", repo.display()));
    }

    setup_wrapper(ctx)?;

    let hooks_dir = git_dir.join("hooks");
    fs::create_dir_all(&hooks_dir)?;

    if pre_commit {
        write_hook(&hooks_dir.join("pre-commit"), PRE_COMMIT, "pre-commit")?;
    }
    if post_checkout {
        write_hook(&hooks_dir.join("post-checkout"), POST_CHECKOUT, "post-checkout")?;
    }

    // Apply skip-worktree to existing symlinks
    let cfg = config::load(&ctx.wiki_root)?;
    let sch = schema::load(&ctx.wiki_root)?;
    let mut count = 0;
    for rel_path in schema::walk(&sch, "") {
        let link = symlink_path(repo, &rel_path, &cfg.doc_filename);
        if link.exists() || link.is_symlink() {
            git::skip_worktree(repo, &link.strip_prefix(repo).unwrap().to_string_lossy());
            count += 1;
        }
    }
    println!("  [done]     skip-worktree on {count} doc symlink(s)");

    Ok(())
}

fn setup_wrapper(ctx: &WikiCtx) -> Result<()> {
    let wrapper = ctx.wiki_root.join("wiki");
    fs::write(&wrapper, WRAPPER)?;
    set_executable(&wrapper)?;
    println!("  [created]  .agent-wiki/wiki  (wrapper script)");
    Ok(())
}

pub fn setup_agents_dir(ctx: &WikiCtx) -> Result<()> {
    let agents = ctx.agents_dir();
    fs::create_dir_all(&agents)?;

    // Symlinks into templates/ so agents/ is a single landing spot for guidance docs
    for (src_name, link_name) in [
        ("templates/WIKI_UPDATE.md", "WIKI_UPDATE.md"),
        ("templates/WIKI_MERGE.md", "WIKI_MERGE.md"),
    ] {
        let src = ctx.wiki_root.join(src_name);
        let link = agents.join(link_name);
        if link.exists() || link.is_symlink() {
            fs::remove_file(&link)?;
        }
        if src.exists() {
            let rel = crate::paths::relpath(&src, &agents);
            std::os::unix::fs::symlink(&rel, &link)?;
            println!("  [symlink]  .agent-wiki/agents/{link_name} -> {}", rel.display());
        }
    }
    Ok(())
}

fn write_hook(path: &std::path::Path, content: &str, name: &str) -> Result<()> {
    if path.exists() {
        let existing = fs::read_to_string(path)?;
        if !existing.contains("agent-wiki") {
            println!("  [skipped]  {name}  (existing hook not owned by agent-wiki — edit manually)");
            return Ok(());
        }
    }
    fs::write(path, content)?;
    set_executable(path)?;
    println!("  [written]  .git/hooks/{name}");
    Ok(())
}

fn set_executable(path: &std::path::Path) -> Result<()> {
    #[cfg(unix)]
    {
        let mut perms = fs::metadata(path)?.permissions();
        perms.set_mode(perms.mode() | 0o111);
        fs::set_permissions(path, perms)?;
    }
    Ok(())
}
