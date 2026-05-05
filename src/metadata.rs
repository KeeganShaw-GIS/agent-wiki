use anyhow::Result;
use chrono::Local;
use std::collections::HashMap;
use std::fs;
use std::path::Path;

const HEADER_START: &str = "<!-- agent-wiki";
const HEADER_END: &str = "-->";

/// Strip the `<!-- agent-wiki ... -->` header block from doc content.
pub fn strip_header(content: &str) -> String {
    let Some(start) = content.find(HEADER_START) else {
        return content.to_string();
    };
    let Some(end_off) = content[start..].find(HEADER_END) else {
        return content.to_string();
    };
    let after = &content[start + end_off + HEADER_END.len()..];
    after.trim_start_matches('\n').to_string()
}

/// Parse key→value pairs from the header block.
pub fn read_header(doc: &Path) -> HashMap<String, String> {
    let content = fs::read_to_string(doc).unwrap_or_default();
    parse_header_fields(&content)
}

fn parse_header_fields(content: &str) -> HashMap<String, String> {
    let Some(start) = content.find(HEADER_START) else {
        return HashMap::new();
    };
    let Some(end_off) = content[start..].find(HEADER_END) else {
        return HashMap::new();
    };
    let block = &content[start + HEADER_START.len()..start + end_off];
    let mut map = HashMap::new();
    for line in block.lines() {
        if let Some((k, v)) = line.split_once(':') {
            let k = k.trim();
            let v = v.trim();
            if !k.is_empty() {
                map.insert(k.to_string(), v.to_string());
            }
        }
    }
    map
}

pub fn has_header(content: &str) -> bool {
    content.contains(HEADER_START)
}

/// Write (or rewrite) the unified `<!-- agent-wiki ... -->` header onto a doc.
/// Preserves the existing `SourceCommitID` if `source_commit` is `None`.
pub fn write_header(
    doc: &Path,
    rel_path: &str,
    touched_by: &str,
    doc_filename: &str,
    wiki_commit: Option<&str>,
    source_commit: Option<&str>,
) -> Result<()> {
    let existing = if doc.exists() {
        fs::read_to_string(doc)?
    } else {
        String::new()
    };

    let prev = parse_header_fields(&existing);
    let source_commit = source_commit
        .map(str::to_string)
        .or_else(|| prev.get("SourceCommitID").cloned());

    let body = strip_header(&existing);
    let location = if rel_path.is_empty() {
        doc_filename.to_string()
    } else {
        format!("{rel_path}/{doc_filename}")
    };

    let today = Local::now().format("%Y-%m-%d").to_string();
    let mut lines = vec![
        HEADER_START.to_string(),
        "Check .agent-wiki/flags.json before starting doc work.".into(),
        "LLM Guide: .agent-wiki/agents/llm.md".into(),
        "Wiki Index: .agent-wiki/AGENT-INDEX.md".into(),
        String::new(),
        format!("Location: {location}"),
        format!("LastTouchedBy: {touched_by}"),
        format!("ChangeDate: {today}"),
    ];
    if let Some(wc) = wiki_commit {
        lines.push(format!("WikiCommitID: {wc}"));
    }
    if let Some(sc) = source_commit {
        lines.push(format!("SourceCommitID: {sc}"));
    }
    lines.push(HEADER_END.to_string());

    let content = format!("{}\n\n{}", lines.join("\n"), body.trim_start_matches('\n'));
    doc.parent().map(fs::create_dir_all).transpose()?;
    fs::write(doc, content)?;
    Ok(())
}
