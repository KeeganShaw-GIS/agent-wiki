mod common;
use common::*;
use std::fs;

// ── Basic init ────────────────────────────────────────────────────────────────

#[test]
fn creates_agent_wiki_dir() {
    let tmp = tempfile::tempdir().unwrap();
    let repo = make_target_repo(tmp.path());
    init_wiki(&repo);
    assert!(repo.join(".agent-wiki").is_dir());
}

#[test]
fn creates_nested_git_repo() {
    let tmp = tempfile::tempdir().unwrap();
    let repo = make_target_repo(tmp.path());
    init_wiki(&repo);
    assert!(repo.join(".agent-wiki/.git").exists());
}

#[test]
fn creates_schema_yaml() {
    let tmp = tempfile::tempdir().unwrap();
    let repo = make_target_repo(tmp.path());
    let ctx = init_wiki(&repo);
    assert!(ctx.wiki_root.join("schema.yaml").exists());
}

#[test]
fn creates_config_json_with_doc_filename() {
    let tmp = tempfile::tempdir().unwrap();
    let repo = make_target_repo(tmp.path());
    let ctx = init_wiki(&repo);
    let cfg = agent_wiki::config::load(&ctx.wiki_root).unwrap();
    assert_eq!(cfg.doc_filename, "CLAUDE.md");
}

#[test]
fn creates_logs_flags_json() {
    let tmp = tempfile::tempdir().unwrap();
    let repo = make_target_repo(tmp.path());
    let ctx = init_wiki(&repo);
    assert!(ctx.wiki_root.join("logs").join("flags.json").exists());
}

#[test]
fn creates_template_files() {
    let tmp = tempfile::tempdir().unwrap();
    let repo = make_target_repo(tmp.path());
    let ctx = init_wiki(&repo);
    assert!(ctx.templates_dir().join("AGENT.template.md").exists());
    assert!(ctx.templates_dir().join("instructions.md").exists());
    assert!(ctx.templates_dir().join("WIKI_UPDATE.md").exists());
    assert!(ctx.templates_dir().join("WIKI_MERGE.md").exists());
}

#[test]
fn creates_llm_md() {
    let tmp = tempfile::tempdir().unwrap();
    let repo = make_target_repo(tmp.path());
    let ctx = init_wiki(&repo);
    assert!(ctx.wiki_root.join("llm.md").exists());
}

#[test]
fn adds_agent_wiki_to_gitignore() {
    let tmp = tempfile::tempdir().unwrap();
    let repo = make_target_repo(tmp.path());
    init_wiki(&repo);
    let gitignore = fs::read_to_string(repo.join(".gitignore")).unwrap();
    assert!(gitignore.contains(".agent-wiki"));
}

#[test]
fn agent_wiki_has_its_own_gitignore() {
    let tmp = tempfile::tempdir().unwrap();
    let repo = make_target_repo(tmp.path());
    let ctx = init_wiki(&repo);
    let aw_ignore = fs::read_to_string(ctx.wiki_root.join(".gitignore")).unwrap();
    assert!(aw_ignore.contains("logs/"));
    assert!(aw_ignore.contains("symlinks/"));
}

#[test]
fn init_is_idempotent() {
    let tmp = tempfile::tempdir().unwrap();
    let repo = make_target_repo(tmp.path());
    init_wiki(&repo);
    // Second init should not fail
    let ctx = init_wiki(&repo);
    assert!(ctx.wiki_root.join("schema.yaml").exists());
}

#[test]
fn creates_root_doc_symlink() {
    let tmp = tempfile::tempdir().unwrap();
    let repo = make_target_repo(tmp.path());
    let ctx = init_wiki(&repo);
    // After init (which calls push), root symlink should exist
    let link = repo.join("CLAUDE.md");
    assert!(
        link.is_symlink() || ctx.docs_root().join("CLAUDE.md").exists(),
        "root doc or symlink should exist after init"
    );
}

// ── Config ────────────────────────────────────────────────────────────────────

#[test]
fn custom_doc_filename_stored_in_config() {
    let tmp = tempfile::tempdir().unwrap();
    let repo = make_target_repo(tmp.path());
    let ctx = agent_wiki::commands::init::run_in(
        repo.clone(),
        agent_wiki::commands::init::InitArgs {
            doc_filename: "AGENTS.md".into(),
            no_detect_target_docs: true,
            no_hooks: true,
            wiki_remote: None,
        },
    )
    .unwrap();
    let cfg = agent_wiki::config::load(&ctx.wiki_root).unwrap();
    assert_eq!(cfg.doc_filename, "AGENTS.md");
}

// ── Schema ────────────────────────────────────────────────────────────────────

#[test]
fn initial_schema_has_root_plus() {
    let tmp = tempfile::tempdir().unwrap();
    let repo = make_target_repo(tmp.path());
    let ctx = init_wiki(&repo);
    let sch = agent_wiki::schema::load(&ctx.wiki_root).unwrap();
    let paths = agent_wiki::schema::walk(&sch, "");
    assert!(paths.contains(&String::new()), "root+ should be in schema");
}
