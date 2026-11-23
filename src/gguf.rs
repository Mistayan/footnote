//! A GGUF file's header metadata, read without llama.cpp (#556): `models import` refuses a file that is not an embedding model
//! before copying it, and builds without llama.cpp can still say why. Only the scalar and string keys are kept; arrays (the
//! tokenizer's vocabulary) are skipped by seeking. Format: <https://github.com/ggml-org/ggml/blob/master/docs/gguf.md>.
use anyhow::{Context, Result, bail, ensure};
use std::{
    collections::HashMap,
    fs::File,
    io::{BufReader, Read, Seek},
    path::Path,
};

/// A kept metadata value.
#[derive(Debug, Clone, PartialEq)]
pub enum Meta {
    Int(i128),
    Float(f64),
    Bool(bool),
    Str(String),
}

/// Bounds against a corrupt or hostile header: a real one has a few dozen keys with short names and values.
const MAX_KEYS: u64 = 1 << 16;
const MAX_KEY: u64 = 1 << 16;
const MAX_KEPT_STRING: u64 = 1 << 20;
const MAX_ARRAY: u64 = 1 << 26;

pub struct Header {
    pub keys: HashMap<String, Meta>,
}

impl Header {
    pub fn str(&self, key: &str) -> Option<&str> {
        match self.keys.get(key)? {
            Meta::Str(s) => Some(s),
            _ => None,
        }
    }
    pub fn int(&self, key: &str) -> Option<i128> {
        match self.keys.get(key)? {
            Meta::Int(n) => Some(*n),
            _ => None,
        }
    }
}

/// The embedding facts `models import` needs, from the header.
#[derive(Debug, PartialEq)]
pub struct Embedding {
    pub architecture: String,
    pub name: String,
    /// "mean", "cls" or "last": the pooling `llama::Gguf::load` takes.
    pub pooling: &'static str,
    pub dimension: usize,
    pub context: usize,
    /// `general.license` as the file declares it, empty when it does not.
    pub license: String,
}

pub fn read(path: &Path) -> Result<Header> {
    let f = File::open(path).with_context(|| format!("cannot read {}", path.display()))?;
    read_from(&mut BufReader::new(f))
        .with_context(|| format!("{} is not a GGUF file", path.display()))
}

fn read_from(r: &mut (impl Read + Seek)) -> Result<Header> {
    let mut magic = [0u8; 4];
    r.read_exact(&mut magic)?;
    ensure!(&magic == b"GGUF", "no GGUF signature");
    let version = u32_(r)?;
    ensure!(
        matches!(version, 2 | 3),
        "GGUF version {version} is not supported"
    );
    let _tensors = u64_(r)?;
    let count = u64_(r)?;
    ensure!(count <= MAX_KEYS, "implausible key count {count}");
    let mut keys = HashMap::new();
    for _ in 0..count {
        let len = u64_(r)?;
        ensure!(len <= MAX_KEY, "implausible key length {len}");
        let key = string(r, len)?;
        let kind = u32_(r)?;
        if let Some(v) = value(r, kind)? {
            keys.insert(key, v);
        }
    }
    Ok(Header { keys })
}

/// One value of type `kind`; `None` for an array (skipped).
fn value(r: &mut (impl Read + Seek), kind: u32) -> Result<Option<Meta>> {
    Ok(Some(match kind {
        0 => Meta::Int(bytes::<1>(r)?[0].into()),
        1 => Meta::Int(i8::from_le_bytes(bytes(r)?).into()),
        2 => Meta::Int(u16::from_le_bytes(bytes(r)?).into()),
        3 => Meta::Int(i16::from_le_bytes(bytes(r)?).into()),
        4 => Meta::Int(u32_(r)?.into()),
        5 => Meta::Int(i32::from_le_bytes(bytes(r)?).into()),
        6 => Meta::Float(f32::from_le_bytes(bytes(r)?).into()),
        7 => Meta::Bool(bytes::<1>(r)?[0] != 0),
        8 => {
            let len = u64_(r)?;
            if len > MAX_KEPT_STRING {
                skip(r, len)?;
                return Ok(None);
            }
            Meta::Str(string(r, len)?)
        }
        9 => {
            let (inner, n) = (u32_(r)?, u64_(r)?);
            ensure!(n <= MAX_ARRAY, "implausible array length {n}");
            match width(inner) {
                Some(w) => skip(r, w * n)?,
                None if inner == 8 => {
                    for _ in 0..n {
                        let len = u64_(r)?;
                        skip(r, len)?;
                    }
                }
                None => bail!("unsupported GGUF array of type {inner}"),
            }
            return Ok(None);
        }
        10 => Meta::Int(u64_(r)?.into()),
        11 => Meta::Int(i64::from_le_bytes(bytes(r)?).into()),
        12 => Meta::Float(f64::from_le_bytes(bytes(r)?)),
        other => bail!("unknown GGUF value type {other}"),
    }))
}

fn width(kind: u32) -> Option<u64> {
    match kind {
        0 | 1 | 7 => Some(1),
        2 | 3 => Some(2),
        4..=6 => Some(4),
        10..=12 => Some(8),
        _ => None,
    }
}

fn bytes<const N: usize>(r: &mut impl Read) -> Result<[u8; N]> {
    let mut b = [0u8; N];
    r.read_exact(&mut b).context("the header ends early")?;
    Ok(b)
}
fn u32_(r: &mut impl Read) -> Result<u32> {
    Ok(u32::from_le_bytes(bytes(r)?))
}
fn u64_(r: &mut impl Read) -> Result<u64> {
    Ok(u64::from_le_bytes(bytes(r)?))
}
fn string(r: &mut impl Read, len: u64) -> Result<String> {
    let mut b = Vec::new();
    r.take(len).read_to_end(&mut b)?;
    ensure!(b.len() as u64 == len, "the header ends early");
    Ok(String::from_utf8_lossy(&b).into_owned())
}
fn skip(r: &mut impl Seek, n: u64) -> Result<()> {
    r.seek_relative(i64::try_from(n).context("implausible length")?)?;
    Ok(())
}

impl Header {
    /// The embedding facts, or the reason this file is not an embedding model: a chat model or a reranker would otherwise
    /// import fine and fail at the first recall.
    pub fn embedding(&self) -> Result<Embedding> {
        let arch = self
            .str("general.architecture")
            .context("the GGUF file names no architecture (general.architecture)")?;
        let pooling = match self.int(&format!("{arch}.pooling_type")) {
            Some(1) => "mean",
            Some(2) => "cls",
            Some(3) => "last",
            Some(4) => {
                bail!("this {arch} model is a reranker (rank pooling), not an embedding model")
            }
            _ => bail!(
                "this {arch} model declares no embedding pooling ({arch}.pooling_type): it is not an embedding model, or one llama.cpp cannot pool"
            ),
        };
        let dimension = self
            .int(&format!("{arch}.embedding_length"))
            .and_then(|d| usize::try_from(d).ok())
            .filter(|d| (1..=1 << 16).contains(d))
            .with_context(|| {
                format!("the GGUF file gives no embedding width ({arch}.embedding_length)")
            })?;
        Ok(Embedding {
            architecture: arch.into(),
            name: self.str("general.name").unwrap_or_default().into(),
            pooling,
            dimension,
            context: self
                .int(&format!("{arch}.context_length"))
                .and_then(|c| usize::try_from(c).ok())
                .unwrap_or(512),
            license: self
                .str("general.license")
                .unwrap_or_default()
                .trim()
                .into(),
        })
    }
}

/// A minimal GGUF header with these keys and no tensors, for tests (the import tests write one instead of a real model).
#[cfg(test)]
pub fn synthetic(keys: &[(&str, Meta)]) -> Vec<u8> {
    let mut b = b"GGUF".to_vec();
    b.extend(3u32.to_le_bytes());
    b.extend(0u64.to_le_bytes());
    // a tokenizer-like array of strings, to prove arrays are skipped
    b.extend((keys.len() as u64 + 1).to_le_bytes());
    let put_str = |b: &mut Vec<u8>, s: &str| {
        b.extend((s.len() as u64).to_le_bytes());
        b.extend(s.as_bytes());
    };
    put_str(&mut b, "tokenizer.ggml.tokens");
    b.extend(9u32.to_le_bytes());
    b.extend(8u32.to_le_bytes());
    b.extend(2u64.to_le_bytes());
    put_str(&mut b, "<pad>");
    put_str(&mut b, "hello");
    for (k, v) in keys {
        put_str(&mut b, k);
        match v {
            Meta::Int(n) => {
                b.extend(4u32.to_le_bytes());
                b.extend((*n as u32).to_le_bytes());
            }
            Meta::Float(x) => {
                b.extend(6u32.to_le_bytes());
                b.extend((*x as f32).to_le_bytes());
            }
            Meta::Bool(x) => {
                b.extend(7u32.to_le_bytes());
                b.push(u8::from(*x));
            }
            Meta::Str(s) => {
                b.extend(8u32.to_le_bytes());
                put_str(&mut b, s);
            }
        }
    }
    b
}

#[cfg(test)]
mod tests {
    use super::{Meta, read_from, synthetic};
    use std::io::Cursor;

    fn header(keys: &[(&str, Meta)]) -> super::Header {
        read_from(&mut Cursor::new(synthetic(keys))).unwrap()
    }

    #[test]
    fn reads_an_embedding_header_and_skips_arrays() {
        let h = header(&[
            ("general.architecture", Meta::Str("bert".into())),
            ("general.name", Meta::Str("Tiny Embed".into())),
            ("general.license", Meta::Str("apache-2.0".into())),
            ("bert.pooling_type", Meta::Int(1)),
            ("bert.embedding_length", Meta::Int(384)),
            ("bert.context_length", Meta::Int(512)),
        ]);
        let e = h.embedding().unwrap();
        assert_eq!(
            (
                e.pooling,
                e.dimension,
                e.context,
                e.name.as_str(),
                e.license.as_str()
            ),
            ("mean", 384, 512, "Tiny Embed", "apache-2.0")
        );
    }

    #[test]
    fn refuses_chat_models_rerankers_and_non_gguf() {
        let chat = header(&[
            ("general.architecture", Meta::Str("llama".into())),
            ("llama.embedding_length", Meta::Int(4096)),
        ]);
        assert!(
            chat.embedding()
                .unwrap_err()
                .to_string()
                .contains("not an embedding model")
        );
        let rerank = header(&[
            ("general.architecture", Meta::Str("bert".into())),
            ("bert.pooling_type", Meta::Int(4)),
            ("bert.embedding_length", Meta::Int(384)),
        ]);
        assert!(
            rerank
                .embedding()
                .unwrap_err()
                .to_string()
                .contains("reranker")
        );
        assert!(read_from(&mut Cursor::new(b"PK\x03\x04 not a model".to_vec())).is_err());
        // cut short in the middle of the keys
        let mut cut = synthetic(&[("general.architecture", Meta::Str("bert".into()))]);
        cut.truncate(cut.len() - 2);
        assert!(read_from(&mut Cursor::new(cut)).is_err());
    }
}
