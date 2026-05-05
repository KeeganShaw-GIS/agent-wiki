use anyhow::Result;
use std::fs;
use std::os::unix::fs::symlink;

use crate::{
    config,
    git,
    logs,
    metadata,
    paths::{display_doc, doc_path, relpath, symlink_path},
    root::WikiCtx,
    schema::{self, untracked},
};

pub struct PushCounts {
    pub symlinks: usize,
    pub new_docs: usize,
}

pub fn run(ctx: &WikiCtx, verify: bool) -> Result<PushCounts> {
    let cfg = config::load(&ctx.wiki_root)?;
    let sch = schema::load(&ctx.wiki_root)?;
    let managed = schema::walk(&sch, "");
    let repo = ctx.repo_root();

    if verify {
        run_verify(ctx, &managed, &cfg.doc_filename)?;
        return Ok(PushCounts { symlinks: 0, new_docs: 0 });
    }

    generate_agent_index(ctx, &sch, &managed, &cfg.doc_filename)?;

    let mut counts = PushCounts { symlinks: 0, new_docs: 0 };
    let head = git::head_hash(repo);

    for rel_path in &managed {
        let was_new = !doc_path(ctx, rel_path, &cfg.doc_filename).exists();
        ensure_doc(ctx, rel_path, &cfg.doc_filename, "manual", head.as_deref())?;
        if was_new && !rel_path.is_empty() {
            counts.new_docs += 1;
        }

        let link = symlink_path(repo, rel_path, &cfg.doc_filename);
        let wiki_doc = doc_path(ctx, rel_path, &cfg.doc_filename);

        if link.is_symlink() {
            // Already a symlink — leave it.
        } else if link.exists() {
            absorb_real_file(&link, &wiki_doc)?;
            metadata::write_header(
                &wiki_doc, rel_path, "agent-wiki push",
                &cfg.doc_filename, None, head.as_deref(),
            )?;
            counts.symlinks += 1;
        } else {
            make_symlink(&link, &wiki_doc)?;
            counts.symlinks += 1;
        }

        git::skip_worktree(repo, &link.strip_prefix(repo).unwrap().to_string_lossy());
    }

    handle_untracked(ctx, &sch, &cfg.doc_filename)?;
    logs::clear_flags(
        &ctx.wiki_root,
        &["docs_out_of_sync"],
    );

    Ok(counts)
}

pub fn ensure_doc(
    ctx: &WikiCtx,
    rel_path: &str,
    doc_filename: &str,
    source: &str,
    source_commit: Option<&str>,
) -> Result<()> {
    let dp = doc_path(ctx, rel_path, doc_filename);
    if dp.exists() {
        return Ok(());
    }

    dp.parent().map(fs::create_dir_all).transpose()?;

    let instructions = ctx.templates_dir().join("instructions.md");
    let template = ctx.templates_dir().join("AGENT.template.md");

    let body = if rel_path.is_empty() && instructions.exists() {
        fs::read_to_string(&instructions)?
    } else if template.exists() {
        fs::read_to_string(&template)?
            .replace("{path}", if rel_path.is_empty() { "root" } else { rel_path })
    } else {
        format!("# Doc: {}\n\nNot yet populated.\n", if rel_path.is_empty() { "root" } else { rel_path })
    };

    fs::write(&dp, &body)?;

    let repo = ctx.repo_root();
    let head = git::head_hash(repo);
    metadata::write_header(
        &dp, rel_path, "agent-wiki check-paths",
        doc_filename,
        git::head_hash(&ctx.wiki_root).as_deref(),
        source_commit.or(head.as_deref()),
    )?;

    let display = display_doc(rel_path, doc_filename);
    println!("  [created]  {display}");

    if !rel_path.is_empty() {
        logs::append_new_entry(&ctx.wiki_root, rel_path, &display, source);
        logs::set_flag(&ctx.wiki_root, "new_entry", serde_json::Value::Bool(true));
    }

    Ok(())
}

fn make_symlink(link: &std::path::Path, target: &std::path::Path) -> Result<()> {
    link.parent().map(fs::create_dir_all).transpose()?;
    let rel = relpath(target, link.parent().unwrap());
    symlink(&rel, link)?;
    println!(
        "  [symlink]  {} -> {}",
        link.file_name().unwrap_or_default().to_string_lossy(),
        rel.display()
    );
    Ok(())
}

fn absorb_real_file(link: &std::path::Path, wiki_doc: &std::path::Path) -> Result<()> {
    wiki_doc.parent().map(fs::create_dir_all).transpose()?;
    fs::copy(link, wiki_doc)?;
    fs::remove_file(link)?;
    make_symlink(link, wiki_doc)?;
    println!("  [absorbed] {}", link.display());
    Ok(())
}

fn handle_untracked(ctx: &WikiCtx, sch: &serde_yaml::Mapping, doc_filename: &str) -> Result<()> {
    let repo = ctx.repo_root();
    for rel_path in untracked(sch, "") {
        let wiki_doc = doc_path(ctx, &rel_path, doc_filename);
        let link = symlink_path(repo, &rel_path, doc_filename);

        if link.is_symlink() {
            fs::remove_file(&link)?;
            println!("  [untracked] removed symlink {}", link.strip_prefix(repo).unwrap_or(&link).display());
        }
        if wiki_doc.exists() {
            link.parent().map(fs::create_dir_all).transpose()?;
            let clean = metadata::strip_header(&fs::read_to_string(&wiki_doc)?);
            fs::write(&link, clean)?;
            fs::remove_file(&wiki_doc)?;
            println!("  [untracked] moved wiki doc → {}", link.strip_prefix(repo).unwrap_or(&link).display());
        }

    }
    Ok(())
}

fn run_verify(ctx: &WikiCtx, managed: &[String], doc_filename: &str) -> Result<()> {
    println!("Verifying symlinks...");
    let repo = ctx.repo_root();
    let mut broken = Vec::new();
    let mut untracked_list = Vec::new();

    for rel_path in managed {
        let link = symlink_path(repo, rel_path, doc_filename);
        let wiki_doc = doc_path(ctx, rel_path, doc_filename);

        if !link.exists() && !link.is_symlink() {
            if wiki_doc.exists() {
                println!("  [missing]  {}", link.display());
                broken.push(rel_path.clone());
                make_symlink(&link, &wiki_doc)?;
            } else {
                println!("  [untracked] {}", link.display());
                untracked_list.push(rel_path.clone());
                ensure_doc(ctx, rel_path, doc_filename, "verify", None)?;
                make_symlink(&link, &wiki_doc)?;
            }
        } else if link.is_symlink() && !link.exists() {
            println!("  [dead]     {}", link.display());
            broken.push(rel_path.clone());
            fs::remove_file(&link)?;
            ensure_doc(ctx, rel_path, doc_filename, "verify", None)?;
            make_symlink(&link, &wiki_doc)?;
        }
    }

    scan_orphaned(ctx, managed, doc_filename)?;

    if broken.is_empty() && untracked_list.is_empty() {
        println!("  All symlinks OK.");
        logs::clear_flags(&ctx.wiki_root, &["docs_out_of_sync"]);
    } else {
        let mut flag_val = serde_json::json!({});
        if !broken.is_empty() {
            flag_val["broken"] = serde_json::json!(broken);
        }
        if !untracked_list.is_empty() {
            flag_val["untracked"] = serde_json::json!(untracked_list);
        }
        logs::set_flag(&ctx.wiki_root, "docs_out_of_sync", flag_val);
    }
    Ok(())
}

fn scan_orphaned(ctx: &WikiCtx, managed: &[String], doc_filename: &str) -> Result<()> {
    let repo = ctx.repo_root();
    let managed_links: Vec<_> = managed
        .iter()
        .map(|rp| symlink_path(repo, rp, doc_filename))
        .collect();

    for entry in walkdir::WalkDir::new(repo)
        .into_iter()
        .filter_map(|e| e.ok())
        .filter(|e| e.file_name().to_string_lossy() == doc_filename)
    {
        let path = entry.path();
        // Skip .git and .agent-wiki
        if path.components().any(|c| {
            let s = c.as_os_str().to_string_lossy();
            s == ".git" || s == ".agent-wiki"
        }) {
            continue;
        }
        if managed_links.contains(&path.to_path_buf()) {
            continue;
        }
        let content = if path.is_symlink() {
            match path.read_link().ok().and_then(|t| fs::read_to_string(t).ok()) {
                Some(c) => c,
                None => continue,
            }
        } else {
            match fs::read_to_string(path) {
                Ok(c) => c,
                Err(_) => continue,
            }
        };
        if !metadata::has_header(&content) {
            continue;
        }
        let clean = metadata::strip_header(&content);
        if path.is_symlink() {
            fs::remove_file(path)?;
            fs::write(path, clean)?;
        } else {
            fs::write(path, clean)?;
        }
        println!("  [orphan-ejected] {}", path.strip_prefix(repo).unwrap_or(path).display());
    }
    Ok(())
}

fn generate_agent_index(
    ctx: &WikiCtx,
    sch: &serde_yaml::Mapping,
    _managed: &[String],
    doc_filename: &str,
) -> Result<()> {
    let repo_name = ctx
        .repo_root()
        .file_name()
        .and_then(|n| n.to_str())
        .unwrap_or("repo")
        .to_string();

    fn tree_lines(
        node: &serde_yaml::Mapping,
        prefix: &str,
        indent: usize,
        doc_filename: &str,
    ) -> Vec<String> {
        let mut lines = Vec::new();
        for (k, v) in node {
            let raw = k.as_str().unwrap_or("");
            if raw.ends_with('~') {
                continue;
            }
            let seg = raw.trim_end_matches(|c| c == '+' || c == '~');
            let path = if seg == "root" {
                String::new()
            } else if prefix.is_empty() {
                seg.to_string()
            } else {
                format!("{prefix}/{seg}")
            };
            let pad = "  ".repeat(indent);
            if raw.ends_with('+') {
                let label = if path.is_empty() { "Root" } else { seg };
                let doc_link = if path.is_empty() {
                    format!("docs/{doc_filename}")
                } else {
                    format!("docs/{path}/{doc_filename}")
                };
                lines.push(format!("{pad}- [{label}]({doc_link})"));
            }
            if let serde_yaml::Value::Mapping(children) = v {
                let next_indent = if raw.ends_with('+') { indent + 1 } else { indent };
                lines.extend(tree_lines(children, &path, next_indent, doc_filename));
            }
        }
        lines
    }

    let tree = tree_lines(sch, "", 0, doc_filename).join("\n");
    let content = format!(
        "# Agent Index — {repo_name}\n\n\
         > Auto-generated by `agent-wiki push`. Do not edit — re-run push to regenerate.\n\n\
         ## Documentation Tree\n\n\
         {tree}\n\n\
         ## Agent Resources\n\n\
         - [Wiki Reference](llm.md)\n\
         - [Update Guide](agents/WIKI_UPDATE.md)\n\
         - [Merge Guide](agents/WIKI_MERGE.md)\n\n\
         ## Status\n\n\
         Check `logs/flags.json` before starting doc work.\n"
    );

    fs::write(ctx.agent_index_path(), content)?;
    Ok(())
}
