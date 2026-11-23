//! Opt-in sharing of complete hook deliveries with a session-bound MCP connection.
use serde::{Deserialize, Serialize};
use serde_json::{Value, json};
use sha2::{Digest, Sha256};
use std::{
    collections::BTreeMap,
    fs,
    io::Read,
    path::{Path, PathBuf},
};

/// The host writes this in private state before starting the bound turn. A stdio
/// MCP request carries no Codex thread identity of its own.
#[derive(Deserialize)]
pub(crate) struct Binding {
    session: String,
    project: String,
    cwd: PathBuf,
}

impl Binding {
    pub(crate) fn load() -> Option<Self> {
        let path = PathBuf::from(std::env::var_os("FOOTNOTE_CONTEXT_SESSION_FILE")?);
        if !path.is_absolute() || footnote_core::no_links(&path).is_err() {
            return None;
        }
        let mut bytes = Vec::new();
        let file = fs::File::open(path).ok()?;
        if !file.metadata().ok()?.is_file() {
            return None;
        }
        file.take(8193).read_to_end(&mut bytes).ok()?;
        if bytes.len() > 8192 {
            return None;
        }
        let mut binding: Self = serde_json::from_slice(&bytes).ok()?;
        if !valid_session(&binding.session)
            || binding.project.is_empty()
            || binding.project == "global"
            || !binding.cwd.is_absolute()
        {
            return None;
        }
        binding.cwd = binding.cwd.canonicalize().ok()?;
        Some(binding)
    }

    pub(crate) fn accepts(&self, session: &str, project: &str, cwd: &Path) -> bool {
        self.session == session
            && self.project == project
            && cwd.canonicalize().is_ok_and(|cwd| cwd == self.cwd)
    }

    pub(crate) fn session(&self) -> &str {
        &self.session
    }

    pub(crate) fn for_project(&self, project: &str) -> bool {
        self.project == project
    }

    fn key(&self, db: &Path) -> Option<[u8; 32]> {
        let db = db.canonicalize().ok()?;
        let mut hash = Sha256::new();
        for field in [
            self.session.as_bytes(),
            self.project.as_bytes(),
            self.cwd.as_os_str().as_encoded_bytes(),
            db.as_os_str().as_encoded_bytes(),
        ] {
            hash.update((field.len() as u64).to_le_bytes());
            hash.update(field);
        }
        Some(hash.finalize().into())
    }
}

fn valid_session(session: &str) -> bool {
    session.len() == 36
        && session.bytes().enumerate().all(|(index, byte)| {
            if matches!(index, 8 | 13 | 18 | 23) {
                byte == b'-'
            } else {
                byte.is_ascii_hexdigit()
            }
        })
}

#[derive(Deserialize, Serialize)]
pub(crate) struct Delivery {
    key: [u8; 32],
    project: String,
    shown: BTreeMap<i64, [u8; 32]>,
}

impl Delivery {
    pub(crate) fn new(binding: Binding, db: &Path) -> Option<Self> {
        Some(Self {
            key: binding.key(db)?,
            project: binding.project,
            shown: BTreeMap::new(),
        })
    }

    pub(crate) fn matches(&self, binding: &Binding, db: &Path) -> bool {
        binding.for_project(&self.project) && binding.key(db) == Some(self.key)
    }

    pub(crate) fn note(&mut self, hit: &Value, delivered: &str) {
        if self.shown.len() < 256
            && hit["scope"].as_str() == Some(self.project.as_str())
            && hit["text"].as_str() == Some(delivered)
            && let Some(id) = hit["id"].as_i64()
        {
            self.shown.insert(id, Sha256::digest(delivered).into());
        }
    }

    pub(crate) fn mark(&self, hit: &mut Value) {
        if let (Some(id), Some(text), Some(path)) = (
            hit["id"].as_i64(),
            hit["text"].as_str(),
            hit["path"].as_str(),
        ) && path.starts_with(footnote_search::store::MEMORY_PREFIX)
            && (hit["status"].is_null() || hit["status"] == "indexed")
            && self
                .shown
                .get(&id)
                .is_some_and(|hash| *hash == <[u8; 32]>::from(Sha256::digest(text)))
        {
            *hit = json!({"id": id, "already_shown": true});
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn only_complete_project_memories_match_the_bound_session_and_db() {
        let root = tempfile::tempdir().unwrap();
        let db = root.path().join("memory.db");
        let other = root.path().join("other.db");
        fs::write(&db, "").unwrap();
        fs::write(&other, "").unwrap();
        let binding = |session: &str| Binding {
            session: session.into(),
            project: "project".into(),
            cwd: root.path().canonicalize().unwrap(),
        };
        let a = binding("019a9d4e-918b-7000-a027-38fe53eec000");
        let b = binding("019a9d4e-918b-7000-a027-38fe53eec001");
        assert!(valid_session(a.session()));
        assert!(!valid_session("../other"));
        let mut delivery = Delivery::new(binding(a.session()), &db).unwrap();
        assert!(delivery.matches(&a, &db));
        assert!(!delivery.matches(&b, &db));
        assert!(!delivery.matches(&a, &other));
        assert!(!a.accepts(a.session(), "different", root.path()));
        delivery.note(
            &json!({"id": 1, "text": "complete", "scope": "project"}),
            "complete",
        );
        delivery.note(
            &json!({"id": 2, "text": "long text", "scope": "project"}),
            "long",
        );
        delivery.note(
            &json!({"id": 3, "text": "global rule", "scope": "global"}),
            "global rule",
        );
        let hit = |id, text, path| json!({"id": id, "text": text, "path": path});
        let mut match_hit = hit(1, "complete", "memory:a");
        delivery.mark(&mut match_hit);
        assert_eq!(match_hit, json!({"id": 1, "already_shown": true}));
        for mut unseen in [
            hit(1, "updated", "memory:b"),
            hit(1, "complete", "document.txt"),
            hit(2, "long text", "memory:b"),
            hit(3, "global rule", "memory:c"),
        ] {
            let before = unseen.clone();
            delivery.mark(&mut unseen);
            assert_eq!(unseen, before);
        }
    }
}
