mod common;
use common::*;
use std::fs;

fn setup(tmp: &tempfile::TempDir) -> (agent_wiki::root::WikiCtx, std::path::PathBuf) {
    let repo = make_target_repo(tmp.path());
    let ctx = init_wiki(&repo);
    write_rich_schema(&ctx);
    agent_wiki::commands::push::run(&ctx, false).unwrap();
    (ctx, repo)
}

// ── Symlink creation ──────────────────────────────────────────────────────────

#[test]
fn creates_symlinks_for_all_schema_paths() {
    let tmp = tempfile::tempdir().unwrap();
    let (ctx, repo) = setup(&tmp);
    let cfg = agent_wiki::config::load(&ctx.wiki_root).unwrap();
    let sch = agent_wiki::schema::load(&ctx.wiki_root).unwrap();
    for rel_path in agent_wiki::schema::walk(&sch, "") {
        let link = agent_wiki::paths::symlink_path(&repo, &rel_path, &cfg.doc_filename);
        assert!(is_valid_symlink(&link), "symlink missing for {rel_path}");
    }
}

#[test]
fn symlinks_point_into_agent_wiki_docs() {
    let tmp = tempfile::tempdir().unwrap();
    let (ctx, repo) = setup(&tmp);
    let link = repo.join("CLAUDE.md");
    let target = link.read_link().unwrap();
    let resolved = if target.is_absolute() {
        target
    } else {
        repo.join(&target)
    };
    assert!(
        resolved.to_string_lossy().contains(".agent-wiki"),
        "symlink target should be inside .agent-wiki: {}",
        resolved.display()
    );
}

#[test]
fn creates_wiki_docs_for_all_paths() {
    let tmp = tempfile::tempdir().unwrap();
    let (ctx, _repo) = setup(&tmp);
    let cfg = agent_wiki::config::load(&ctx.wiki_root).unwrap();
    let sch = agent_wiki::schema::load(&ctx.wiki_root).unwrap();
    for rel_path in agent_wiki::schema::walk(&sch, "") {
        let dp = agent_wiki::paths::doc_path(&ctx, &rel_path, &cfg.doc_filename);
        assert!(dp.exists(), "wiki doc missing for {rel_path}");
    }
}

#[test]
fn wiki_docs_have_header_block() {
    let tmp = tempfile::tempdir().unwrap();
    let (ctx, _repo) = setup(&tmp);
    let cfg = agent_wiki::config::load(&ctx.wiki_root).unwrap();
    let sch = agent_wiki::schema::load(&ctx.wiki_root).unwrap();
    for rel_path in agent_wiki::schema::walk(&sch, "") {
        let dp = agent_wiki::paths::doc_path(&ctx, &rel_path, &cfg.doc_filename);
        let content = fs::read_to_string(&dp).unwrap();
        assert!(
            content.contains("<!-- agent-wiki"),
            "doc missing header for {rel_path}"
        );
    }
}

// ── AGENT-INDEX ───────────────────────────────────────────────────────────────

#[test]
fn creates_agent_index() {
    let tmp = tempfile::tempdir().unwrap();
    let (ctx, _repo) = setup(&tmp);
    assert!(ctx.agent_index_path().exists());
}

#[test]
fn agent_index_contains_doc_links() {
    let tmp = tempfile::tempdir().unwrap();
    let (ctx, _repo) = setup(&tmp);
    let content = fs::read_to_string(ctx.agent_index_path()).unwrap();
    assert!(content.contains("Root"), "AGENT-INDEX missing Root entry");
    assert!(content.contains("docs/CLAUDE.md"), "AGENT-INDEX missing docs/ links");
}

// ── Absorption of real files ──────────────────────────────────────────────────

#[test]
fn absorbs_real_file_into_wiki() {
    let tmp = tempfile::tempdir().unwrap();
    let repo = make_target_repo(tmp.path());
    let ctx = init_wiki(&repo);
    write_rich_schema(&ctx);

    // Place a real file at src/CLAUDE.md before push
    let real = repo.join("src").join("CLAUDE.md");
    fs::write(&real, "# Real doc\n").unwrap();

    agent_wiki::commands::push::run(&ctx, false).unwrap();

    // Should now be a symlink
    assert!(is_valid_symlink(&real), "real file not converted to symlink");
    // Wiki doc should contain the content
    let wiki_doc = ctx.docs_root().join("src").join("CLAUDE.md");
    let content = fs::read_to_string(&wiki_doc).unwrap();
    assert!(content.contains("Real doc"), "wiki doc missing absorbed content");
}

// ── New-entry log ─────────────────────────────────────────────────────────────

#[test]
fn new_paths_logged_to_new_entry_log() {
    let tmp = tempfile::tempdir().unwrap();
    let (ctx, _repo) = setup(&tmp);
    let entries = agent_wiki::logs::load_new_entries(&ctx.wiki_root);
    // root path is NOT logged (only non-root new paths)
    let logged_paths: Vec<&str> = entries.iter().map(|e| e.rel_path.as_str()).collect();
    assert!(logged_paths.contains(&"src"), "src not in new-entry log");
    assert!(logged_paths.contains(&"frontend"), "frontend not in new-entry log");
}

// ── Verify ────────────────────────────────────────────────────────────────────

#[test]
fn verify_restores_deleted_symlink() {
    let tmp = tempfile::tempdir().unwrap();
    let (ctx, repo) = setup(&tmp);
    let link = repo.join("CLAUDE.md");
    fs::remove_file(&link).unwrap();
    assert!(!link.exists());

    agent_wiki::commands::push::run(&ctx, true).unwrap();
    assert!(is_valid_symlink(&link), "verify should restore missing symlink");
}

#[test]
fn verify_repairs_dead_symlink() {
    let tmp = tempfile::tempdir().unwrap();
    let (ctx, repo) = setup(&tmp);
    let link = repo.join("CLAUDE.md");
    // Create a dangling symlink manually
    let target = link.read_link().unwrap();
    fs::remove_file(&link).unwrap();
    std::os::unix::fs::symlink("nonexistent/path/CLAUDE.md", &link).unwrap();
    let _ = target; // just to keep reference

    agent_wiki::commands::push::run(&ctx, true).unwrap();
    assert!(is_valid_symlink(&link), "verify should repair dead symlink");
}

// ── Untracked paths ───────────────────────────────────────────────────────────

#[test]
fn untracked_path_removes_symlink_and_restores_file() {
    let tmp = tempfile::tempdir().unwrap();
    let (ctx, repo) = setup(&tmp);
    // Change src to ~
    fs::write(
        ctx.wiki_root.join("schema.yaml"),
        "root+:\n  src~:\n  frontend+:\n    components+:\n",
    )
    .unwrap();
    agent_wiki::commands::push::run(&ctx, false).unwrap();

    let link = repo.join("src/CLAUDE.md");
    assert!(!link.is_symlink(), "symlink should be removed for ~ path");
    assert!(link.exists(), "real file should exist for ~ path");
}

#[test]
fn untracked_file_has_no_wiki_header() {
    let tmp = tempfile::tempdir().unwrap();
    let (ctx, repo) = setup(&tmp);
    fs::write(
        ctx.wiki_root.join("schema.yaml"),
        "root+:\n  src~:\n  frontend+:\n    components+:\n",
    )
    .unwrap();
    agent_wiki::commands::push::run(&ctx, false).unwrap();

    let content = fs::read_to_string(repo.join("src/CLAUDE.md")).unwrap();
    assert!(!content.contains("<!-- agent-wiki"), "untracked file should have header stripped");
}
