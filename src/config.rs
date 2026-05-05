use anyhow::{bail, Result};
use serde::{Deserialize, Serialize};
use std::fs;
use std::path::Path;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Config {
    #[serde(default = "default_doc_filename")]
    pub doc_filename: String,
}

fn default_doc_filename() -> String {
    "CLAUDE.md".into()
}

impl Default for Config {
    fn default() -> Self {
        Self {
            doc_filename: default_doc_filename(),
        }
    }
}

pub fn load(wiki_root: &Path) -> Result<Config> {
    let path = wiki_root.join("config.json");
    if !path.exists() {
        bail!(
            "No config.json found in .agent-wiki/. Run:\n  agent-wiki init"
        );
    }
    let text = fs::read_to_string(&path)?;
    Ok(serde_json::from_str(&text)?)
}

pub fn save(wiki_root: &Path, config: &Config) -> Result<()> {
    let path = wiki_root.join("config.json");
    fs::write(path, serde_json::to_string_pretty(config)? + "\n")?;
    Ok(())
}
