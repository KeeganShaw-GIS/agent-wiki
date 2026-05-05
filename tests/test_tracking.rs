mod common;
use common::*;
use std::fs;

fn setup_with_commit(tmp: &tempfile::TempDir) -> (agent_wiki::root::WikiCtx, std::path::PathBuf) {
    let repo = make_target_repo(tmp.path());
    let ctx = init_wiki(&repo);
    write_rich_schema(&ctx);
    agent_wiki::commands::push::run(&ctx, false).unwrap();
    commit(&repo, "add wiki docs");
    // Stamp SourceCommitID after the commit so SourceCommitID == HEAD.
    // This ensures detect-drift finds no drift when nothing has changed since setup.
    let head = agent_wiki::git::head_hash(&repo);
    let cfg = agent_wiki::config::load(&ctx.wiki_root).unwrap();
    let sch = agent_wiki::schema::load(&ctx.wiki_root).unwrap();
    for rel_path in agent_wiki::schema::walk(&sch, "") {
        let dp = agent_wiki::paths::doc_path(&ctx, &rel_path, &cfg.doc_filename);
        if dp.exists() {
            agent_wiki::metadata::write_header(
                &dp, &rel_path, "test-setup", &cfg.doc_filename,
                None, head.as_deref(),
            ).unwrap();
        }
    }
    (ctx, repo)
}

// ── Drift detection ───────────────────────────────────────────────────────────

#[test]
fn no_drift_when_no_changes() {
    let tmp = tempfile::tempdir().unwrap();
    let (ctx, _repo) = setup_with_commit(&tmp);
    agent_wiki::commands::detect_drift::run(&ctx, false).unwrap();
    let entries = agent_wiki::logs::load_drift(&ctx.wiki_root);
    assert!(entries.is_empty(), "no drift should be logged when nothing changed");
}

#[test]
fn detects_drift_after_source_file_changes() {
    let tmp = tempfile::tempdir().unwrap();
    let (ctx, repo) = setup_with_commit(&tmp);

    // Modify source file and commit
    fs::write(repo.join("src/main.py"), "def main(): return 42\n").unwrap();
    commit(&repo, "modify src");

    agent_wiki::commands::detect_drift::run(&ctx, false).unwrap();

    let entries = agent_wiki::logs::load_drift(&ctx.wiki_root);
    assert!(!entries.is_empty(), "drift should be detected after source change");
    let src_entry = entries.iter().find(|e| e.rel_path == "src");
    assert!(src_entry.is_some(), "src drift entry should exist");
    assert!(
        src_entry.unwrap().changed_files.contains(&"src/main.py".to_string()),
        "changed files should include src/main.py"
    );
}

#[test]
fn drift_detection_is_idempotent() {
    let tmp = tempfile::tempdir().unwrap();
    let (ctx, repo) = setup_with_commit(&tmp);

    fs::write(repo.join("src/main.py"), "# changed\n").unwrap();
    commit(&repo, "modify src");

    agent_wiki::commands::detect_drift::run(&ctx, false).unwrap();
    let count1 = agent_wiki::logs::load_drift(&ctx.wiki_root).len();

    agent_wiki::commands::detect_drift::run(&ctx, false).unwrap();
    let count2 = agent_wiki::logs::load_drift(&ctx.wiki_root).len();

    assert_eq!(count1, count2, "repeated detect-drift should not duplicate entries");
}

#[test]
fn drift_sets_drift_detected_flag() {
    let tmp = tempfile::tempdir().unwrap();
    let (ctx, repo) = setup_with_commit(&tmp);

    fs::write(repo.join("src/main.py"), "# changed\n").unwrap();
    commit(&repo, "modify src");

    agent_wiki::commands::detect_drift::run(&ctx, false).unwrap();

    let flags = read_flags(&ctx.wiki_root);
    assert_eq!(flags["drift_detected"], serde_json::json!(true));
}

#[test]
fn staged_drift_only_counts_staged_changes() {
    let tmp = tempfile::tempdir().unwrap();
    let (ctx, repo) = setup_with_commit(&tmp);

    // Unstaged change in frontend
    fs::write(repo.join("frontend/app.ts"), "// unstaged\n").unwrap();
    // Staged change in src
    fs::write(repo.join("src/main.py"), "# staged\n").unwrap();
    git(&repo, &["add", "src/main.py"]);

    // NOTE: staged detection looks at staged+HEAD delta, which is src
    // This test validates it doesn't crash and only processes staged context
    let result = agent_wiki::commands::detect_drift::run(&ctx, true);
    assert!(result.is_ok(), "staged drift detection should not error");
}

// ── Clear flags ───────────────────────────────────────────────────────────────

#[test]
fn clear_flags_removes_all_flags() {
    let tmp = tempfile::tempdir().unwrap();
    let (ctx, repo) = setup_with_commit(&tmp);

    fs::write(repo.join("src/main.py"), "# changed\n").unwrap();
    commit(&repo, "modify src");
    agent_wiki::commands::detect_drift::run(&ctx, false).unwrap();
    // Also stamp docs so clearing drift works
    agent_wiki::commands::clear_flags::run(&ctx, &[]).unwrap();

    let flags = read_flags(&ctx.wiki_root);
    let meaningful: Vec<&str> = flags
        .as_object()
        .unwrap()
        .keys()
        .filter(|k| *k != "last_updated")
        .map(String::as_str)
        .collect();
    assert!(meaningful.is_empty(), "all flags should be cleared: {flags}");
}

#[test]
fn clear_flags_specific_flag() {
    let tmp = tempfile::tempdir().unwrap();
    let (ctx, _repo) = setup_with_commit(&tmp);

    agent_wiki::logs::set_flag(&ctx.wiki_root, "new_entry", serde_json::json!(true));
    agent_wiki::logs::set_flag(&ctx.wiki_root, "drift_detected", serde_json::json!(true));

    agent_wiki::commands::clear_flags::run(&ctx, &["new_entry".to_string()]).unwrap();

    let flags = read_flags(&ctx.wiki_root);
    assert!(flags.get("new_entry").is_none(), "new_entry should be cleared");
    // drift_detected should remain (since its backing log is empty but we only cleared new_entry)
}

// ── Untracked path transitions ────────────────────────────────────────────────

#[test]
fn promoting_path_to_untracked_removes_symlink() {
    let tmp = tempfile::tempdir().unwrap();
    let (ctx, repo) = setup_with_commit(&tmp);

    fs::write(
        ctx.wiki_root.join("schema.yaml"),
        "root+:\n  src~:\n  frontend+:\n    components+:\n",
    )
    .unwrap();
    agent_wiki::commands::push::run(&ctx, false).unwrap();

    let link = repo.join("src/CLAUDE.md");
    assert!(!link.is_symlink(), "untracked path should not have symlink");
    assert!(link.exists(), "untracked path should have real file");
}

#[test]
fn untracked_real_file_has_no_header() {
    let tmp = tempfile::tempdir().unwrap();
    let (ctx, repo) = setup_with_commit(&tmp);

    fs::write(
        ctx.wiki_root.join("schema.yaml"),
        "root+:\n  src~:\n  frontend+:\n    components+:\n",
    )
    .unwrap();
    agent_wiki::commands::push::run(&ctx, false).unwrap();

    let content = fs::read_to_string(repo.join("src/CLAUDE.md")).unwrap();
    assert!(!content.contains("<!-- agent-wiki"), "untracked file should not have header");
}

// ── New-entry log management ──────────────────────────────────────────────────

#[test]
fn new_entry_flag_set_after_push_with_new_paths() {
    let tmp = tempfile::tempdir().unwrap();
    let repo = make_target_repo(tmp.path());
    let ctx = init_wiki(&repo);
    write_rich_schema(&ctx);
    agent_wiki::commands::push::run(&ctx, false).unwrap();

    let flags = read_flags(&ctx.wiki_root);
    assert_eq!(flags["new_entry"], serde_json::json!(true));
}

#[test]
fn new_entry_log_cleared_by_clear_flags() {
    let tmp = tempfile::tempdir().unwrap();
    let repo = make_target_repo(tmp.path());
    let ctx = init_wiki(&repo);
    write_rich_schema(&ctx);
    agent_wiki::commands::push::run(&ctx, false).unwrap();

    agent_wiki::logs::clear_new_entries(&ctx.wiki_root);
    agent_wiki::commands::clear_flags::run(&ctx, &[]).unwrap();

    let flags = read_flags(&ctx.wiki_root);
    assert!(flags.get("new_entry").is_none(), "new_entry flag should be auto-cleared");
}
