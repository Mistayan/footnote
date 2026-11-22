//! Text extraction for Library: runs the bundled Python helper (`tools/extract.py`) on one document snapshot and reads
//! its pages back as JSON. The interpreter is `FOOTNOTE_PYTHON` or the `.venv` beside the binary or checkout.
use anyhow::{Context, Result, bail};
use serde::Deserialize;
use std::{
    fs,
    process::{Command, Stdio},
    time::Duration,
};
use wait_timeout::ChildExt;

#[derive(Deserialize)]
pub struct Page {
    pub page: i64,
    pub text: String,
}
#[derive(Deserialize)]
pub struct Extraction {
    pub status: String,
    pub extractor: String,
    pub pages: Vec<Page>,
}

const HELPER: &str = include_str!("../../../tools/extract.py");

pub(crate) fn helper_hash() -> &'static str {
    static HASH: std::sync::OnceLock<String> = std::sync::OnceLock::new();
    HASH.get_or_init(|| footnote_core::hash(HELPER.as_bytes()))
}

pub fn extract(bytes: &[u8], ext: &str) -> Result<Extraction> {
    let scratch = footnote_core::scratch_dir()?;
    let dir = tempfile::tempdir_in(scratch)?;
    let source = dir.path().join(format!("snapshot.{ext}"));
    fs::write(&source, bytes)?;
    let output = dir.path().join("output.json");
    let python = if let Some(path) = std::env::var_os("FOOTNOTE_PYTHON") {
        std::path::PathBuf::from(path)
    } else {
        let exe = std::env::current_exe()?;
        let bin = exe.parent().context("engine directory")?;
        let interpreter = if cfg!(windows) {
            ".venv/Scripts/python.exe"
        } else {
            ".venv/bin/python"
        };
        // Cargo builds normally live at <checkout>/target/<profile>/footnote.
        let root = bin
            .parent()
            .filter(|p| p.ends_with("target"))
            .and_then(|p| p.parent())
            .unwrap_or(bin);
        root.join(interpreter)
    };
    let mut cmd = Command::new(python);
    cmd.args(["-I", "-c", HELPER])
        .arg(source)
        .stdout(fs::File::create(&output)?)
        .stderr(Stdio::null())
        .stdin(Stdio::null());
    // Untrusted documents are parsed here: never hand the agent's credentials on.
    footnote_core::helper_env(&mut cmd);
    let mut child = cmd.spawn()?;
    let Some(status) = child.wait_timeout(Duration::from_secs(120))? else {
        child.kill()?;
        child.wait()?;
        bail!("extractor timed out");
    };
    if !status.success() || fs::metadata(&output)?.len() > 8_000_000 {
        bail!("extractor failed or exceeded output limit");
    }
    let mut result: Extraction = serde_json::from_slice(&fs::read(output)?)?;
    if result.pages.len() > 100
        || result.pages.iter().map(|p| p.text.len()).sum::<usize>() > 4_000_000
    {
        bail!("extractor response exceeded limits");
    }
    result
        .extractor
        .push_str(&format!(";helper-sha256={}", helper_hash()));
    result.extractor.push_str(";chunker-v2");
    Ok(result)
}
