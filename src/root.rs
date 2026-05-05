use anyhow::{bail, Result};
use std::path::{Path, PathBuf};

/// Context derived from locating the `.agent-wiki/` directory.
pub struct WikiCtx {
    /// `.agent-wiki/` — the nested wiki git repo
    pub wiki_root: PathBuf,
}

impl WikiCtx {
    pub fn new(wiki_root: PathBuf) -> Self {
        Self { wiki_root }
    }

    /// Parent of `.agent-wiki/` — the target (code) repository root.
    pub fn repo_root(&self) -> &Path {
        self.wiki_root
            .parent()
            .expect("wiki_root always has a parent")
    }

    pub fn docs_root(&self) -> PathBuf {
        self.wiki_root.join("docs")
    }

    pub fn schema_path(&self) -> PathBuf {
        self.wiki_root.join("schema.yaml")
    }

    pub fn config_path(&self) -> PathBuf {
        self.wiki_root.join("config.json")
    }

    pub fn logs_dir(&self) -> PathBuf {
        self.wiki_root.join("logs")
    }

    pub fn templates_dir(&self) -> PathBuf {
        self.wiki_root.join("templates")
    }

    pub fn agent_index_path(&self) -> PathBuf {
        self.wiki_root.join("AGENT-INDEX.md")
    }

    pub fn agents_dir(&self) -> PathBuf {
        self.wiki_root.join("agents")
    }
}

/// Walk up from `cwd` to find the nearest `.agent-wiki/` containing `schema.yaml`.
pub fn find_wiki_ctx() -> Result<WikiCtx> {
    let cwd = std::env::current_dir()?;
    for dir in cwd.ancestors() {
        let candidate = dir.join(".agent-wiki");
        if candidate.join("schema.yaml").exists() {
            return Ok(WikiCtx::new(candidate));
        }
    }
    bail!("No .agent-wiki/ found. Run: agent-wiki init")
}

/// Walk up from `cwd` to find the nearest directory containing `.git/`.
pub fn find_git_root() -> Result<PathBuf> {
    let cwd = std::env::current_dir()?;
    for dir in cwd.ancestors() {
        if dir.join(".git").exists() {
            return Ok(dir.to_path_buf());
        }
    }
    bail!("Not inside a git repository. Run agent-wiki init from within a git repo.")
}
