use anyhow::{anyhow, Result};
use serde_yaml::{Mapping, Value};
use std::fs;
use std::path::Path;

pub fn load(wiki_root: &Path) -> Result<Mapping> {
    let text = fs::read_to_string(wiki_root.join("schema.yaml"))?;
    let val: Value = serde_yaml::from_str(&text)?;
    match val {
        Value::Mapping(m) => Ok(normalize(m)),
        _ => Err(anyhow!("schema.yaml root must be a YAML mapping")),
    }
}

/// serde_yaml deserialises bare keys (e.g. `root+:`) as Value::Null.
/// Normalise them to empty Mappings so the rest of the code can assume
/// every value is either a Mapping or a Null-free leaf.
fn normalize(m: Mapping) -> Mapping {
    m.into_iter()
        .map(|(k, v)| {
            let v = match v {
                Value::Null => Value::Mapping(Mapping::new()),
                Value::Mapping(child) => Value::Mapping(normalize(child)),
                other => other,
            };
            (k, v)
        })
        .collect()
}

pub fn save(wiki_root: &Path, schema: &Mapping, doc_filename: &str) -> Result<()> {
    let header = format!(
        "# Keys ending with + have a {doc_filename} in docs/ and a symlink in the target.\n\
         # Keys ending with ~ are explicitly untracked (real file stays in target).\n\
         # Keys without a suffix are structural only (nesting containers, no doc).\n"
    );
    let body = dump_mapping(schema, 0);
    fs::write(wiki_root.join("schema.yaml"), format!("{header}{body}\n"))?;
    Ok(())
}

fn dump_mapping(node: &Mapping, indent: usize) -> String {
    let pad = "  ".repeat(indent);
    node.iter()
        .map(|(k, v)| {
            let key = k.as_str().unwrap_or("");
            let mut parts = vec![format!("{pad}{key}:")];
            if let Value::Mapping(children) = v {
                if !children.is_empty() {
                    parts.push(dump_mapping(children, indent + 1));
                }
            }
            parts.join("\n")
        })
        .collect::<Vec<_>>()
        .join("\n")
}

fn parse_suffix(raw: &str) -> (&str, char) {
    if let Some(s) = raw.strip_suffix('+') {
        return (s, '+');
    }
    if let Some(s) = raw.strip_suffix('~') {
        return (s, '~');
    }
    (raw, '\0')
}

fn build_path(prefix: &str, segment: &str) -> String {
    if segment == "root" {
        String::new()
    } else if prefix.is_empty() {
        segment.to_string()
    } else {
        format!("{prefix}/{segment}")
    }
}

/// Return all managed (`+`) paths in schema order.
pub fn walk(node: &Mapping, prefix: &str) -> Vec<String> {
    let mut out = Vec::new();
    for (k, v) in node {
        let raw = k.as_str().unwrap_or("");
        let (seg, suffix) = parse_suffix(raw);
        let path = build_path(prefix, seg);
        if suffix == '+' {
            out.push(path.clone());
        }
        if suffix != '~' {
            if let Value::Mapping(children) = v {
                out.extend(walk(children, &path));
            }
        }
    }
    out
}

/// Return all explicitly untracked (`~`) paths.
pub fn untracked(node: &Mapping, prefix: &str) -> Vec<String> {
    let mut out = Vec::new();
    for (k, v) in node {
        let raw = k.as_str().unwrap_or("");
        let (seg, suffix) = parse_suffix(raw);
        let path = build_path(prefix, seg);
        if suffix == '~' {
            out.push(path.clone());
            if let Value::Mapping(children) = v {
                out.extend(untracked(children, &path));
            }
        } else if let Value::Mapping(children) = v {
            out.extend(untracked(children, &path));
        }
    }
    out
}

/// Add `rel_path` to the schema as a `+` node, creating intermediate nodes as needed.
pub fn add_path(schema: &mut Mapping, rel_path: &str) {
    let root_key = find_key(schema, "root");
    let root_key_str = root_key.unwrap_or_else(|| "root+".into());

    if rel_path.is_empty() {
        // Promote root to root+ if needed
        if !root_key_str.ends_with('+') {
            let val = schema
                .remove(&Value::String(root_key_str))
                .unwrap_or(Value::Mapping(Mapping::new()));
            schema.insert(Value::String("root+".into()), val);
        }
        return;
    }

    // Ensure root+ exists
    if !schema.contains_key(&Value::String(root_key_str.clone())) {
        schema.insert(
            Value::String(root_key_str.clone()),
            Value::Mapping(Mapping::new()),
        );
    }

    let root_val = schema.get_mut(&Value::String(root_key_str)).and_then(|v| {
        if let Value::Mapping(m) = v {
            Some(m)
        } else {
            None
        }
    });

    if let Some(node) = root_val {
        let parts: Vec<&str> = rel_path.split('/').collect();
        add_path_to_node(node, &parts);
    }
}

fn add_path_to_node(node: &mut Mapping, parts: &[&str]) {
    if parts.is_empty() {
        return;
    }
    let part = parts[0];
    let is_last = parts.len() == 1;

    let existing_key = find_key(node, part);
    let target_key = if is_last {
        format!("{part}+")
    } else {
        existing_key.clone().unwrap_or_else(|| part.to_string())
    };

    if let Some(old) = existing_key {
        if old != target_key {
            let val = node
                .remove(&Value::String(old))
                .unwrap_or(Value::Mapping(Mapping::new()));
            node.insert(Value::String(target_key.clone()), val);
        }
    } else {
        node.insert(
            Value::String(target_key.clone()),
            Value::Mapping(Mapping::new()),
        );
    }

    if parts.len() > 1 {
        if let Some(Value::Mapping(child)) = node.get_mut(&Value::String(target_key)) {
            add_path_to_node(child, &parts[1..]);
        }
    }
}

/// Find a key in a mapping by its base segment (ignoring `+`/`~` suffixes).
fn find_key(node: &Mapping, segment: &str) -> Option<String> {
    node.keys().find_map(|k| {
        let s = k.as_str()?;
        let base = s.trim_end_matches(|c| c == '+' || c == '~');
        if base == segment {
            Some(s.to_string())
        } else {
            None
        }
    })
}

pub fn new_default() -> Mapping {
    let mut m = Mapping::new();
    m.insert(
        Value::String("root+".into()),
        Value::Mapping(Mapping::new()),
    );
    m
}

/// Return all ancestor paths of `rel_path` that exist in `all_paths`.
pub fn ancestor_paths(rel_path: &str, all_paths: &[String]) -> Vec<String> {
    if rel_path.is_empty() {
        return vec![];
    }
    let parts: Vec<&str> = rel_path.split('/').collect();
    let mut ancestors = Vec::new();
    for i in 0..parts.len() {
        let candidate = if i == 0 {
            String::new()
        } else {
            parts[..i].join("/")
        };
        if candidate != rel_path && all_paths.contains(&candidate) {
            ancestors.push(candidate);
        }
    }
    ancestors
}

/// Return the most-specific schema path that is a prefix of `file_path`.
pub fn best_match(file_path: &str, paths: &[String]) -> Option<String> {
    let mut best: Option<&String> = None;
    for p in paths {
        if p.is_empty() {
            if !file_path.contains('/') && best.is_none() {
                best = Some(p);
            }
        } else if file_path == p || file_path.starts_with(&format!("{p}/")) {
            match best {
                None => best = Some(p),
                Some(b) if p.len() > b.len() => best = Some(p),
                _ => {}
            }
        }
    }
    best.cloned()
}
