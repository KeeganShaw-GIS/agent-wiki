/// End-to-end happy path test.
///
/// Artifacts are written to `target/e2e-output/` in the workspace root so you
/// can inspect the full directory structure after running:
///
///   cargo test --test test_e2e -- --nocapture
///
mod common;
use common::*;
use std::fs;
use std::path::PathBuf;

/// Returns the fixed output directory, cleared and recreated each run.
fn e2e_dir() -> PathBuf {
    let dir = PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("target/e2e-output");
    if dir.exists() {
        fs::remove_dir_all(&dir).unwrap();
    }
    fs::create_dir_all(&dir).unwrap();
    dir
}

// ── Happy path ────────────────────────────────────────────────────────────────

/// Full workflow: init → push → pull (absorb) → untrack → add path → push
/// → two commits (pre-commit stamps drift on second) → clear-flags resolves.
#[test]
fn full_workflow() {
    let out = e2e_dir();
    let repo = make_target_repo(&out);
    let ctx = init_wiki(&repo);

    // 1. Write schema and push — creates docs + symlinks
    write_rich_schema(&ctx);
    agent_wiki::commands::push::run(&ctx, false).unwrap();

    assert!(is_valid_symlink(&repo.join("src/CLAUDE.md")), "src symlink");
    assert!(is_valid_symlink(&repo.join("frontend/CLAUDE.md")), "frontend symlink");
    println!("[step 1] push OK — symlinks created");

    // 2. Pull — absorb a doc that already exists in the target repo
    fs::create_dir_all(repo.join("api")).unwrap();
    fs::write(repo.join("api/CLAUDE.md"), "# API routes\n").unwrap();
    agent_wiki::commands::pull::run(&ctx, "repo").unwrap();

    assert!(ctx.docs_root().join("api/CLAUDE.md").exists(), "api doc absorbed");
    let flags = read_flags(&ctx.wiki_root);
    assert_eq!(flags["new_entry"], serde_json::json!(true));
    println!("[step 2] pull OK — api/CLAUDE.md absorbed");

    // 3. Untrack frontend (+ → ~) and push — symlinks removed, real files restored
    fs::write(
        ctx.wiki_root.join("schema.yaml"),
        "root+:\n  src+:\n  frontend~:\n    components~:\n  api+:\n",
    )
    .unwrap();
    agent_wiki::commands::push::run(&ctx, false).unwrap();

    assert!(!repo.join("frontend/CLAUDE.md").is_symlink(), "frontend untracked");
    assert!(repo.join("frontend/CLAUDE.md").exists(), "frontend real file remains");
    println!("[step 3] untrack OK — frontend symlink removed, real file present");

    // 4. Add a new tracked path — push logs it as new_entry
    fs::create_dir_all(repo.join("services")).unwrap();
    fs::write(repo.join("services/auth.py"), "def login(): pass\n").unwrap();
    fs::write(
        ctx.wiki_root.join("schema.yaml"),
        "root+:\n  src+:\n  frontend~:\n    components~:\n  api+:\n  services+:\n",
    )
    .unwrap();
    agent_wiki::commands::push::run(&ctx, false).unwrap();

    assert!(is_valid_symlink(&repo.join("services/CLAUDE.md")), "services symlink");
    let entries = agent_wiki::logs::load_new_entries(&ctx.wiki_root);
    assert!(entries.iter().any(|e| e.rel_path == "services"), "services in new-entry log");
    println!("[step 4] new path OK — services/CLAUDE.md created, new_entry logged");

    // 5. Stamp SourceCommitID and commit so detect-drift has a baseline
    commit(&repo, "wiki setup");
    let head = agent_wiki::git::head_hash(&repo);
    let cfg = agent_wiki::config::load(&ctx.wiki_root).unwrap();
    let sch = agent_wiki::schema::load(&ctx.wiki_root).unwrap();
    for rel_path in agent_wiki::schema::walk(&sch, "") {
        let dp = agent_wiki::paths::doc_path(&ctx, &rel_path, &cfg.doc_filename);
        if dp.exists() {
            agent_wiki::metadata::write_header(
                &dp, &rel_path, "e2e-setup", &cfg.doc_filename,
                None, head.as_deref(),
            ).unwrap();
        }
    }

    // 6. Modify src and commit — detect-drift should find src changed
    fs::write(repo.join("src/main.py"), "def main(): return 42\n").unwrap();
    git(&repo, &["add", "src/main.py"]);
    commit(&repo, "feat: update src");

    agent_wiki::commands::detect_drift::run(&ctx, false).unwrap();

    let drift = agent_wiki::logs::load_drift(&ctx.wiki_root);
    assert!(drift.iter().any(|e| e.rel_path == "src"), "src drift detected");
    let flags = read_flags(&ctx.wiki_root);
    assert_eq!(flags["drift_detected"], serde_json::json!(true));
    println!("[step 5+6] drift OK — src drift detected after commit");

    // 7. Clear flags — stamps SourceCommitID to HEAD, clears drift_detected
    let original_src_commit = {
        let dp = agent_wiki::paths::doc_path(&ctx, "src", &cfg.doc_filename);
        agent_wiki::metadata::read_header(&dp)
            .get("SourceCommitID").cloned().unwrap_or_default()
    };
    agent_wiki::commands::clear_flags::run(&ctx, &[]).unwrap();

    let flags = read_flags(&ctx.wiki_root);
    assert!(flags.get("drift_detected").is_none(), "drift_detected cleared");
    let new_src_commit = {
        let dp = agent_wiki::paths::doc_path(&ctx, "src", &cfg.doc_filename);
        agent_wiki::metadata::read_header(&dp)
            .get("SourceCommitID").cloned().unwrap_or_default()
    };
    assert_ne!(original_src_commit, new_src_commit, "SourceCommitID stamped to new HEAD");
    println!("[step 7] clear-flags OK — drift_detected cleared, SourceCommitID stamped");

    println!("\nArtifacts at: {}", out.display());
    println!("  repo/          ← target repo with symlinks");
    println!("  repo/.agent-wiki/  ← nested wiki git repo");
}
