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

// ── Scoped eject ──────────────────────────────────────────────────────────────

#[test]
fn scoped_eject_converts_symlink_to_real_file() {
    let tmp = tempfile::tempdir().unwrap();
    let (ctx, repo) = setup(&tmp);
    let link = repo.join("src/CLAUDE.md");
    assert!(is_valid_symlink(&link));

    agent_wiki::commands::eject::run(&ctx, Some("src"), false).unwrap();

    assert!(!link.is_symlink(), "symlink should be replaced");
    assert!(link.is_file(), "real file should exist after eject");
}

#[test]
fn ejected_file_has_no_wiki_header() {
    let tmp = tempfile::tempdir().unwrap();
    let (ctx, repo) = setup(&tmp);
    agent_wiki::commands::eject::run(&ctx, Some("src"), false).unwrap();

    let content = fs::read_to_string(repo.join("src/CLAUDE.md")).unwrap();
    assert!(!content.contains("<!-- agent-wiki"), "ejected file should have header stripped");
}

#[test]
fn scoped_eject_backs_up_to_local_edits() {
    let tmp = tempfile::tempdir().unwrap();
    let (ctx, _repo) = setup(&tmp);
    agent_wiki::commands::eject::run(&ctx, Some("src"), false).unwrap();

    let backup = ctx.wiki_root.join("logs").join("local-edits").join("src.md");
    assert!(backup.exists(), "backup should be created in logs/local-edits/");
}

#[test]
fn scoped_eject_removes_doc_from_wiki() {
    // After eject the wiki doc content is preserved but the symlink in the repo is gone.
    let tmp = tempfile::tempdir().unwrap();
    let (ctx, repo) = setup(&tmp);
    agent_wiki::commands::eject::run(&ctx, Some("src"), false).unwrap();

    assert!(!repo.join("src/CLAUDE.md").is_symlink(), "symlink should be gone after eject");
    assert!(repo.join("src/CLAUDE.md").is_file(), "real file should exist after eject");
}

#[test]
fn scoped_eject_preserves_other_symlinks() {
    let tmp = tempfile::tempdir().unwrap();
    let (ctx, repo) = setup(&tmp);
    agent_wiki::commands::eject::run(&ctx, Some("src"), false).unwrap();

    assert!(is_valid_symlink(&repo.join("CLAUDE.md")), "root symlink should remain");
    assert!(is_valid_symlink(&repo.join("frontend/CLAUDE.md")), "frontend symlink should remain");
}

#[test]
fn scoped_eject_invalid_path_errors() {
    let tmp = tempfile::tempdir().unwrap();
    let (ctx, _repo) = setup(&tmp);
    let result = agent_wiki::commands::eject::run(&ctx, Some("nonexistent"), false);
    assert!(result.is_err(), "eject with invalid scope should error");
}

#[test]
fn re_running_push_after_scoped_eject_restores_symlink() {
    let tmp = tempfile::tempdir().unwrap();
    let (ctx, repo) = setup(&tmp);
    agent_wiki::commands::eject::run(&ctx, Some("src"), false).unwrap();

    // Real file now at src/CLAUDE.md
    agent_wiki::commands::push::run(&ctx, false).unwrap();
    // Push absorbs it back to wiki and makes it a symlink again
    assert!(is_valid_symlink(&repo.join("src/CLAUDE.md")), "push after eject should restore symlink");
}

// ── Full eject ────────────────────────────────────────────────────────────────

#[test]
fn full_eject_converts_all_symlinks() {
    let tmp = tempfile::tempdir().unwrap();
    let (ctx, repo) = setup(&tmp);
    agent_wiki::commands::eject::run(&ctx, None, false).unwrap();

    for rel_path in ["", "src", "frontend", "frontend/components"] {
        let link = agent_wiki::paths::symlink_path(&repo, rel_path, "CLAUDE.md");
        assert!(!link.is_symlink(), "symlink should be replaced for {rel_path}");
        assert!(link.is_file(), "real file should exist for {rel_path}");
    }
}

#[test]
fn full_eject_without_purge_preserves_agent_wiki() {
    let tmp = tempfile::tempdir().unwrap();
    let (ctx, _repo) = setup(&tmp);
    agent_wiki::commands::eject::run(&ctx, None, false).unwrap();
    assert!(ctx.wiki_root.exists(), ".agent-wiki should be preserved without --purge");
}

#[test]
fn full_eject_with_purge_removes_agent_wiki() {
    let tmp = tempfile::tempdir().unwrap();
    let (ctx, _repo) = setup(&tmp);
    let wiki_root = ctx.wiki_root.clone();
    agent_wiki::commands::eject::run(&ctx, None, true).unwrap();
    assert!(!wiki_root.exists(), ".agent-wiki should be removed with --purge");
}

#[test]
fn full_eject_backs_up_hooks() {
    let tmp = tempfile::tempdir().unwrap();
    let repo = make_target_repo(tmp.path());
    let ctx = init_wiki(&repo);
    write_rich_schema(&ctx);
    // Install hooks first
    agent_wiki::commands::hook_setup::run(&ctx, true, true).unwrap();
    agent_wiki::commands::push::run(&ctx, false).unwrap();
    agent_wiki::commands::eject::run(&ctx, None, false).unwrap();

    let pre_bak = repo.join(".git/hooks/pre-commit.agent-wiki.bak");
    assert!(pre_bak.exists(), "pre-commit hook should be backed up on full eject");
}

// ── Conflict resolution on eject ─────────────────────────────────────────────

#[test]
fn eject_clears_conflict_log() {
    let tmp = tempfile::tempdir().unwrap();
    let (ctx, _repo) = setup(&tmp);
    // Manually inject a conflict entry
    agent_wiki::logs::append_conflict(
        &ctx.wiki_root,
        agent_wiki::logs::ConflictEntry {
            ts: "2024-01-01T00:00:00Z".into(),
            rel_path: "src".into(),
            repo_file: "src/CLAUDE.md".into(),
            wiki_doc: "docs/src/CLAUDE.md".into(),
            wiki_backup: None,
            resolution: None,
        },
    );
    agent_wiki::commands::eject::run(&ctx, Some("src"), false).unwrap();
    assert!(
        agent_wiki::logs::load_conflicts(&ctx.wiki_root)
            .iter()
            .all(|e| e.rel_path != "src"),
        "conflict entry should be cleared after eject"
    );
}
