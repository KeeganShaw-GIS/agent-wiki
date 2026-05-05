use chrono::Utc;
use serde::{Deserialize, Serialize};
use serde_json::Value;
use std::collections::HashMap;
use std::fs;
use std::path::Path;

fn now_ts() -> String {
    Utc::now().format("%Y-%m-%dT%H:%M:%SZ").to_string()
}

// ── Flags ─────────────────────────────────────────────────────────────────────

pub fn flags_path(wiki_root: &Path) -> std::path::PathBuf {
    wiki_root.join("logs").join("flags.json")
}

pub fn load_flags(wiki_root: &Path) -> HashMap<String, Value> {
    let path = flags_path(wiki_root);
    if !path.exists() {
        return HashMap::new();
    }
    serde_json::from_str(&fs::read_to_string(&path).unwrap_or_default()).unwrap_or_default()
}

pub fn set_flag(wiki_root: &Path, key: &str, value: Value) {
    let mut flags = load_flags(wiki_root);
    flags.insert(key.to_string(), value);
    flags.insert("last_updated".into(), Value::String(now_ts()));
    let dir = wiki_root.join("logs");
    let _ = fs::create_dir_all(&dir);
    let _ = fs::write(flags_path(wiki_root), serde_json::to_string_pretty(&flags).unwrap_or_default() + "\n");
}

pub fn clear_flags(wiki_root: &Path, keys: &[&str]) {
    let mut flags = load_flags(wiki_root);
    let mut changed = false;
    for k in keys {
        if flags.remove(*k).is_some() {
            changed = true;
        }
    }
    if changed {
        flags.insert("last_updated".into(), Value::String(now_ts()));
        let _ = fs::write(flags_path(wiki_root), serde_json::to_string_pretty(&flags).unwrap_or_default() + "\n");
    }
}

// ── Drift log ─────────────────────────────────────────────────────────────────

#[derive(Debug, Serialize, Deserialize)]
pub struct DriftEntry {
    pub ts: String,
    pub trigger: String,
    pub rel_path: String,
    pub wiki_doc: String,
    pub from_commit: String,
    pub to_commit: String,
    pub changed_files: Vec<String>,
    pub parent_paths: Vec<String>,
}

pub fn drift_log_path(wiki_root: &Path) -> std::path::PathBuf {
    wiki_root.join("logs").join("drift.jsonl")
}

pub fn load_drift(wiki_root: &Path) -> Vec<DriftEntry> {
    read_jsonl(drift_log_path(wiki_root))
}

pub fn write_drift(wiki_root: &Path, entries: &[DriftEntry]) {
    let dir = wiki_root.join("logs");
    let _ = fs::create_dir_all(&dir);
    let content = entries
        .iter()
        .filter_map(|e| serde_json::to_string(e).ok())
        .collect::<Vec<_>>()
        .join("\n");
    let _ = fs::write(drift_log_path(wiki_root), if content.is_empty() { String::new() } else { content + "\n" });
}

pub fn clear_drift(wiki_root: &Path) {
    let _ = fs::write(drift_log_path(wiki_root), "");
}

pub fn clear_drift_for(wiki_root: &Path, rel_paths: &[&str], doc_filename: &str) {
    let display_docs: Vec<String> = rel_paths
        .iter()
        .map(|rp| {
            if rp.is_empty() {
                format!("docs/{doc_filename}")
            } else {
                format!("docs/{rp}/{doc_filename}")
            }
        })
        .collect();
    let remaining: Vec<DriftEntry> = load_drift(wiki_root)
        .into_iter()
        .filter(|e| !display_docs.contains(&e.wiki_doc))
        .collect();
    write_drift(wiki_root, &remaining);
}

// ── New-entry log ─────────────────────────────────────────────────────────────

#[derive(Debug, Serialize, Deserialize)]
pub struct NewEntryEntry {
    pub ts: String,
    pub rel_path: String,
    pub doc: String,
    pub source: String,
}

pub fn new_entry_log_path(wiki_root: &Path) -> std::path::PathBuf {
    wiki_root.join("logs").join("new-entry.jsonl")
}

pub fn load_new_entries(wiki_root: &Path) -> Vec<NewEntryEntry> {
    read_jsonl(new_entry_log_path(wiki_root))
}

pub fn append_new_entry(wiki_root: &Path, rel_path: &str, doc: &str, source: &str) {
    let entry = NewEntryEntry {
        ts: now_ts(),
        rel_path: rel_path.to_string(),
        doc: doc.to_string(),
        source: source.to_string(),
    };
    append_jsonl(new_entry_log_path(wiki_root), &entry);
}

pub fn clear_new_entries(wiki_root: &Path) {
    let _ = fs::write(new_entry_log_path(wiki_root), "");
}

pub fn clear_new_entries_for(wiki_root: &Path, rel_paths: &[&str]) {
    let remaining: Vec<NewEntryEntry> = load_new_entries(wiki_root)
        .into_iter()
        .filter(|e| !rel_paths.contains(&e.rel_path.as_str()))
        .collect();
    let dir = wiki_root.join("logs");
    let _ = fs::create_dir_all(&dir);
    let content = remaining
        .iter()
        .filter_map(|e| serde_json::to_string(e).ok())
        .collect::<Vec<_>>()
        .join("\n");
    let _ = fs::write(new_entry_log_path(wiki_root), if content.is_empty() { String::new() } else { content + "\n" });
}

// ── Conflict log ──────────────────────────────────────────────────────────────

#[derive(Debug, Serialize, Deserialize)]
pub struct ConflictEntry {
    pub ts: String,
    pub rel_path: String,
    pub repo_file: String,
    pub wiki_doc: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub wiki_backup: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub resolution: Option<String>,
}

pub fn conflict_log_path(wiki_root: &Path) -> std::path::PathBuf {
    wiki_root.join("logs").join("conflict.jsonl")
}

pub fn load_conflicts(wiki_root: &Path) -> Vec<ConflictEntry> {
    read_jsonl(conflict_log_path(wiki_root))
}

pub fn append_conflict(wiki_root: &Path, entry: ConflictEntry) {
    append_jsonl(conflict_log_path(wiki_root), &entry);
}

pub fn clear_conflicts_for(wiki_root: &Path, rel_paths: &[&str]) {
    let remaining: Vec<ConflictEntry> = load_conflicts(wiki_root)
        .into_iter()
        .filter(|e| !rel_paths.contains(&e.rel_path.as_str()))
        .collect();
    let dir = wiki_root.join("logs");
    let _ = fs::create_dir_all(&dir);
    let content = remaining
        .iter()
        .filter_map(|e| serde_json::to_string(e).ok())
        .collect::<Vec<_>>()
        .join("\n");
    let _ = fs::write(conflict_log_path(wiki_root), if content.is_empty() { String::new() } else { content + "\n" });
}

// ── JSONL helpers ─────────────────────────────────────────────────────────────

fn read_jsonl<T: for<'de> Deserialize<'de>>(path: std::path::PathBuf) -> Vec<T> {
    let text = fs::read_to_string(&path).unwrap_or_default();
    text.lines()
        .filter(|l| !l.trim().is_empty())
        .filter_map(|l| serde_json::from_str(l).ok())
        .collect()
}

fn append_jsonl<T: Serialize>(path: std::path::PathBuf, entry: &T) {
    let line = match serde_json::to_string(entry) {
        Ok(s) => s + "\n",
        Err(_) => return,
    };
    if let Some(dir) = path.parent() {
        let _ = fs::create_dir_all(dir);
    }
    use std::io::Write;
    if let Ok(mut f) = fs::OpenOptions::new().create(true).append(true).open(&path) {
        let _ = f.write_all(line.as_bytes());
    }
}
