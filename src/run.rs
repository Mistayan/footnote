//! Lean D (#243): preservation-first shell command runner (`footnote run`) and reversible local output store (`footnote output`).
//!
//! Core invariants:
//! - Never emit more bytes than the raw command output (including footer and code-graph links); if not smaller, pass raw through.
//! - On any filter error or panic, pass raw output and the exact child exit code through untouched.
//! - Output containing potential credentials is NEVER written to the local handle store (fail-closed).
//! - Preserve tracebacks, failing assertions, compiler spans, error lines, conflict markers, and byte-exact edit anchors.
use anyhow::{Context, Result, bail};
use regex::Regex;
use serde_json::{Value, json};
use std::{
    collections::BTreeMap,
    fs,
    io::{Read, Write},
    path::{Path, PathBuf},
    process::{Command, Stdio},
    sync::OnceLock,
    time::{Duration, SystemTime, UNIX_EPOCH},
};

/// Default threshold above which generic (unrecognized) command output is summarized.
const GENERIC_THRESHOLD_BYTES: usize = 12 * 1024;
/// Minimum stdout size for uniform JSON-array compaction (#381).
const JSON_ARRAY_MIN_BYTES: usize = 2 * 1024;
/// Minimum object count for uniform JSON-array compaction (#381).
const JSON_ARRAY_MIN_ITEMS: usize = 8;
/// Session window (seconds) during which identical consecutive failures collapse to a 3-line repeat delta (#381).
const REPEAT_WINDOW_SECS: u64 = 30 * 60;
/// Maximum number of `(cwd, command)` repeat-run entries retained on disk (#381).
const MAX_REPEAT_ENTRIES: usize = 64;
/// Expire stored raw output handles older than 24 hours.
const HANDLE_TTL_SECS: u64 = 24 * 3600;
/// Cap the local handle store to at most this many files (oldest evicted first).
const MAX_HANDLES: usize = 200;
/// Cap the raw output stored per handle (8 MiB) to bound disk usage.
const MAX_STORE_BYTES: usize = 8 * 1024 * 1024;

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
#[non_exhaustive]
pub enum CommandFamily {
    CargoTest,
    CargoBuild,
    TestRunner,
    Git,
    Search,
    Linter,
    JsonArray,
    Listing,
    Generic,
}

impl CommandFamily {
    #[must_use]
    pub const fn as_str(self) -> &'static str {
        match self {
            Self::CargoTest => "cargo-test",
            Self::CargoBuild => "cargo-build",
            Self::TestRunner => "tests",
            Self::Git => "git",
            Self::Search => "search",
            Self::Linter => "linter",
            Self::JsonArray => "json-array",
            Self::Listing => "listing",
            Self::Generic => "generic",
        }
    }

    #[must_use]
    pub fn parse_override(name: &str) -> Option<Self> {
        match name {
            "cargo-test" => Some(Self::CargoTest),
            "cargo-build" => Some(Self::CargoBuild),
            "tests" => Some(Self::TestRunner),
            "git" => Some(Self::Git),
            "search" => Some(Self::Search),
            "linter" => Some(Self::Linter),
            "json-array" => Some(Self::JsonArray),
            "listing" => Some(Self::Listing),
            "generic" => Some(Self::Generic),
            _ => None,
        }
    }
}

/// Classify a command invocation (`argv`) into its preservation-first filter family.
#[must_use]
pub fn classify_command(cmd: &[String]) -> CommandFamily {
    let Some(first) = cmd.first() else {
        return CommandFamily::Generic;
    };
    let bin = Path::new(first)
        .file_stem()
        .and_then(|s| s.to_str())
        .unwrap_or(first.as_str())
        .to_ascii_lowercase();
    let sub = subcommand_of(cmd).map(str::to_ascii_lowercase);

    match bin.as_str() {
        "cargo" => match sub.as_deref() {
            Some("test" | "nextest") => CommandFamily::CargoTest,
            Some("build" | "check" | "clippy" | "doc" | "b" | "c") => CommandFamily::CargoBuild,
            _ => CommandFamily::Generic,
        },
        "git" => match sub.as_deref() {
            Some("grep") => CommandFamily::Search,
            Some(
                "status" | "diff" | "log" | "branch" | "show" | "fetch" | "pull" | "push"
                | "checkout" | "switch" | "merge" | "rebase" | "add" | "commit" | "worktree"
                | "stash" | "ls-files" | "ls-tree" | "ls-remote" | "blame" | "shortlog" | "reflog"
                | "tag" | "remote" | "clone" | "cherry-pick" | "restore" | "reset" | "rm" | "mv"
                | "clean" | "rev-list" | "submodule",
            ) => CommandFamily::Git,
            _ => CommandFamily::Generic,
        },
        "rg" | "grep" | "egrep" | "fgrep" | "findstr" | "ag" => CommandFamily::Search,
        "ls" => CommandFamily::Listing,
        "pytest" | "jest" | "vitest" | "mocha" => CommandFamily::TestRunner,
        "go" if sub.as_deref() == Some("test") => CommandFamily::TestRunner,
        "node" if cmd.iter().any(|a| a == "--test") => CommandFamily::TestRunner,
        "npm" | "pnpm" | "yarn" | "bun" if matches!(sub.as_deref(), Some("test" | "t")) => {
            CommandFamily::TestRunner
        }
        "python" | "python3" | "py" | "uv" => {
            if cmd.iter().any(|a| a == "pytest" || a == "unittest") {
                CommandFamily::TestRunner
            } else if cmd
                .iter()
                .any(|a| matches!(a.as_str(), "ruff" | "mypy" | "flake8"))
            {
                CommandFamily::Linter
            } else {
                CommandFamily::Generic
            }
        }
        "ruff" | "eslint" | "tsc" | "mypy" | "flake8" | "biome" | "pylint" => CommandFamily::Linter,
        "gh" if matches!(
            sub.as_deref(),
            Some("issue" | "pr" | "run" | "release" | "repo")
        ) && cmd.iter().any(|a| a == "--json") =>
        {
            CommandFamily::JsonArray
        }
        "npx" | "pnpx" | "bunx" => match sub.as_deref() {
            Some("jest" | "vitest" | "mocha" | "playwright") => CommandFamily::TestRunner,
            Some("eslint" | "tsc" | "biome") => CommandFamily::Linter,
            _ => CommandFamily::Generic,
        },
        _ => CommandFamily::Generic,
    }
}

/// The subcommand of `cmd`: its first argument that is not an option, skipping the values of the global options that
/// take one, so `git -C <dir> status` is `status` and `cargo +nightly test` is `test`.
#[must_use]
pub fn subcommand_of(cmd: &[String]) -> Option<&str> {
    let bin = Path::new(cmd.first()?)
        .file_stem()
        .and_then(|s| s.to_str())
        .unwrap_or("")
        .to_ascii_lowercase();
    let takes_value: &[&str] = match bin.as_str() {
        "git" => &[
            "-C",
            "-c",
            "--git-dir",
            "--work-tree",
            "--namespace",
            "--config-env",
        ],
        "cargo" => &["-C", "--config", "-Z"],
        _ => &[],
    };
    let mut args = cmd.iter().skip(1);
    while let Some(a) = args.next() {
        if takes_value.contains(&a.as_str()) {
            args.next();
            continue;
        }
        if a.starts_with('-') || (bin == "cargo" && a.starts_with('+')) {
            continue;
        }
        return Some(a);
    }
    None
}

/// Check whether `footnote` (or `footnote.exe` on Windows) is resolvable on the current `PATH`.
#[must_use]
pub fn footnote_on_path() -> bool {
    let Some(path_var) = std::env::var_os("PATH") else {
        return false;
    };
    let bin_name = if cfg!(windows) {
        "footnote.exe"
    } else {
        "footnote"
    };
    std::env::split_paths(&path_var).any(|dir| dir.join(bin_name).is_file())
}

/// Format an executable path cleanly for POSIX and Windows shells (quoting only if it contains whitespace).
fn format_exe_for_shell(exe: &Path, shell: Shell) -> String {
    let norm = exe.to_string_lossy().replace('\\', "/");
    match (norm.chars().any(char::is_whitespace), shell) {
        (false, _) => norm,
        // PowerShell reads a quoted path as a string, not a command, without the call operator.
        (true, Shell::PowerShell) => format!("& \"{norm}\""),
        (true, Shell::Posix) => format!("\"{norm}\""),
    }
}

/// The shell a command line is written for. It matters only for names the shell resolves itself: in PowerShell `ls`
/// is an alias of `Get-ChildItem`, so `footnote run -- ls` would start a different program.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Shell {
    Posix,
    PowerShell,
}

/// Rewrite the parts of a shell command line that Footnote Lean filters to `footnote run -- <part>`, inside a
/// PreToolUse hook. Returns `None` when nothing is rewritten.
#[must_use]
pub fn rewrite_command(cmd: &str) -> Option<String> {
    rewrite_command_in(cmd, "footnote", Shell::Posix)
}

/// Rewrite a command line written for `shell`.
///
/// Agents rarely send one bare command: they write `cd X && cargo test 2>&1 | tail -5`, `Set-Location X; rg …`,
/// `git status && git diff`. The line is split at top-level `&&`, `||`, `;` and newlines, and each part that runs a
/// filtered program gets `footnote run -- ` in front of that program. Everything else in the line is kept byte for
/// byte, so separators, `cd` and `$env:` statements and exit-code semantics are unchanged (#565).
///
/// A part is left alone when it writes stdout to a file or pipes into anything but `head`, `tail` or
/// `Select-Object -First/-Last`, because filtered output would change what lands there. A part that sends stderr
/// elsewhere (`2>/dev/null`) gets `--raw-stderr`, so the program's stderr still goes where the agent sent it. A part
/// holding a group (`( )`, `{ }`, `$( )`, `@( )`) or an input redirect is left alone, and the parts around it are still
/// rewritten. A line with a heredoc, here-string, backtick, background `&`, unbalanced group or unclosed quote is left
/// whole, since its separators cannot be found safely, and so is a line whose loop or `if` output is piped or
/// redirected (`done | grep x`), since that would carry the body's filtered output.
#[must_use]
pub fn rewrite_command_in(cmd: &str, bin_cmd: &str, shell: Shell) -> Option<String> {
    let inserts = rewrite_points(cmd, shell).ok()?;
    Some(render_rewrite(cmd, bin_cmd, inserts))
}

fn rewrite_points(cmd: &str, shell: Shell) -> Result<Vec<(usize, RunFlags)>, &'static str> {
    if cmd.trim().is_empty() {
        return Err("empty");
    }
    let parts = line_parts(cmd).ok_or("compound")?;
    if parts.iter().any(|p| {
        (p.redirects_stdout || p.redirects_stderr || !p.pipes.is_empty())
            && closes_compound(&cmd[p.start..p.end])
    }) {
        return Err("compound");
    }
    let inserts: Vec<(usize, RunFlags)> = parts
        .iter()
        .filter_map(|part| part_rewrite_point(cmd, part, shell))
        .collect();
    if inserts.is_empty() {
        return Err(
            if parts
                .iter()
                .any(|p| p.opaque || p.redirects_stdout || !p.pipes.is_empty())
            {
                "compound"
            } else {
                "not-covered"
            },
        );
    }
    Ok(inserts)
}

pub(crate) fn shell_for_agent(agent: &str, tool: &str) -> Shell {
    if cfg!(windows) && (agent == "codex" || !tool.eq_ignore_ascii_case("bash")) {
        Shell::PowerShell
    } else {
        Shell::Posix
    }
}

pub(crate) fn would_rewrite(cmd: &str, agent: &str, tool: &str) -> bool {
    rewrite_points(cmd, shell_for_agent(agent, tool)).is_ok()
}

fn render_rewrite(cmd: &str, bin_cmd: &str, inserts: Vec<(usize, RunFlags)>) -> String {
    let mut out = String::with_capacity(cmd.len() + inserts.len() * 48);
    let mut last = 0;
    for (at, flags) in inserts {
        out.push_str(&cmd[last..at]);
        out.push_str(bin_cmd);
        out.push_str(" run ");
        if flags.no_footer {
            out.push_str("--no-footer ");
        }
        if flags.raw_stderr {
            out.push_str("--raw-stderr ");
        }
        out.push_str("-- ");
        last = at;
    }
    out.push_str(&cmd[last..]);
    out.trim().to_string()
}

/// The `footnote run` options a rewritten part needs.
#[derive(Debug, Clone, Copy, Default)]
struct RunFlags {
    /// Output piped into `tail` or `-Last`: the closing note would take one of the last lines.
    no_footer: bool,
    /// Stderr sent elsewhere (`2>/dev/null`, `2>err.txt`): it must not be merged into what the agent reads.
    raw_stderr: bool,
}

/// Whether a part starts with the word that closes a bash loop, `if` or `case`.
fn closes_compound(part: &str) -> bool {
    matches!(part.split_whitespace().next(), Some("done" | "fi" | "esac"))
}

/// One top-level part of a command line: the bytes between `&&`, `||`, `;` and newlines, with the offsets of its `|`
/// pipes, where its output goes, and whether it holds a group or input redirect (`opaque`), which leaves it alone.
struct LinePart {
    start: usize,
    end: usize,
    pipes: Vec<usize>,
    /// Stdout goes to a file or to stderr (`>`, `>>`, `1>`, `>&2`, `&>`, `*>`).
    redirects_stdout: bool,
    /// Stderr goes somewhere other than stdout (`2>file`, `2>/dev/null`); `2>&1` is not counted.
    redirects_stderr: bool,
    opaque: bool,
}

impl LinePart {
    fn at(start: usize) -> Self {
        Self {
            start,
            end: start,
            pipes: Vec::new(),
            redirects_stdout: false,
            redirects_stderr: false,
            opaque: false,
        }
    }
}

/// Split a command line into its top-level parts. Separators inside a group (`( )`, `{ }`, `$( )`, `${ }`, `@( )`,
/// `@{ }`) do not split it; the part holding the group is marked opaque. `None` when the line holds a construct whose
/// separators a quote-aware scan cannot find safely: a heredoc or here-string, a backtick, `$(…)` inside double quotes,
/// a background `&`, an unbalanced group, or an unclosed quote.
fn line_parts(cmd: &str) -> Option<Vec<LinePart>> {
    let b = cmd.as_bytes();
    let n = b.len();
    let mut parts = Vec::new();
    let mut part = LinePart::at(0);
    let close = |parts: &mut Vec<LinePart>, part: &mut LinePart, end: usize, next: usize| {
        part.end = end;
        let done = std::mem::replace(part, LinePart::at(next));
        if !cmd[done.start..done.end].trim().is_empty() {
            parts.push(done);
        }
    };
    let mut depth = 0usize;
    let mut word_start = true;
    let mut i = 0;
    while i < n {
        match b[i] {
            b'\'' => {
                i = i + 1 + cmd[i + 1..].find('\'')? + 1;
                word_start = false;
            }
            b'"' => {
                let mut j = i + 1;
                loop {
                    match b.get(j)? {
                        b'\\' => j += 2,
                        b'"' => break,
                        // PowerShell escapes with a backtick (`"` included), and `$(…)` may hold quotes of its own:
                        // either way the closing quote cannot be found safely.
                        b'`' => return None,
                        b'$' if b.get(j + 1) == Some(&b'(') => return None,
                        b'$' if b.get(j + 1) == Some(&b'{') => {
                            part.opaque = true;
                            j += 2;
                        }
                        _ => j += 1,
                    }
                }
                i = j + 1;
                word_start = false;
            }
            b'\\' => {
                i += 2;
                word_start = false;
            }
            // A top-level backtick continues a PowerShell line or substitutes in bash.
            b'`' | b'\0' => return None,
            b'<' if b.get(i + 1) == Some(&b'<') => return None,
            b'@' if matches!(b.get(i + 1), Some(b'\'' | b'"')) => return None,
            b'<' => {
                // Input redirect or `<(…)`: the program reads something other than the agent's stdin.
                part.opaque = true;
                i += 1;
                word_start = true;
            }
            b'(' | b'{' => {
                depth += 1;
                part.opaque = true;
                i += 1;
                word_start = true;
            }
            b')' | b'}' => {
                depth = depth.checked_sub(1)?;
                i += 1;
                word_start = false;
            }
            b'#' if word_start => {
                while i < n && b[i] != b'\n' {
                    i += 1;
                }
            }
            b'&' if b.get(i + 1) == Some(&b'&') => {
                if depth == 0 {
                    close(&mut parts, &mut part, i, i + 2);
                }
                i += 2;
                word_start = true;
            }
            b'|' if b.get(i + 1) == Some(&b'|') => {
                if depth == 0 {
                    close(&mut parts, &mut part, i, i + 2);
                }
                i += 2;
                word_start = true;
            }
            b';' | b'\n' => {
                if depth == 0 {
                    close(&mut parts, &mut part, i, i + 1);
                }
                i += 1;
                word_start = true;
            }
            b'|' => {
                if depth == 0 {
                    part.pipes.push(i);
                }
                i += 1;
                word_start = true;
            }
            b'>' => {
                // `2>&1` merges stderr into what the agent reads anyway. `2>target` sends stderr away, which
                // `--raw-stderr` keeps working. Any other redirect sends stdout away from the agent.
                let stderr = i > 0 && b[i - 1] == b'2' && (i < 2 || b[i - 2].is_ascii_whitespace());
                i += 1;
                let merges_stderr =
                    stderr && b.get(i) == Some(&b'&') && b.get(i + 1) == Some(&b'1');
                if b.get(i) == Some(&b'&') {
                    i += 1;
                    while i < n && b[i].is_ascii_digit() {
                        i += 1;
                    }
                } else {
                    if b.get(i) == Some(&b'>') {
                        i += 1;
                    }
                    while i < n && matches!(b[i], b' ' | b'\t') {
                        i += 1;
                    }
                    while i < n
                        && !b[i].is_ascii_whitespace()
                        && !matches!(b[i], b';' | b'|' | b'&' | b'(' | b')' | b'{' | b'}')
                    {
                        i += 1;
                    }
                }
                if merges_stderr {
                } else if stderr {
                    part.redirects_stderr = true;
                } else {
                    part.redirects_stdout = true;
                }
                word_start = false;
            }
            b'&' => {
                if b.get(i + 1) == Some(&b'>') {
                    // `&>file`: both streams to a file.
                    part.redirects_stdout = true;
                    i += 2;
                    word_start = false;
                    continue;
                }
                // PowerShell's call operator starts a stage (`& "C:\x\tool.exe" …`); anywhere else `&` backgrounds.
                let stage_start = part.pipes.last().map_or(part.start, |p| p + 1);
                if depth == 0 && !cmd[stage_start..i].trim().is_empty() {
                    return None;
                }
                i += 1;
                word_start = true;
            }
            c if c.is_ascii_whitespace() => {
                i += 1;
                word_start = true;
            }
            _ => {
                i += 1;
                word_start = false;
            }
        }
    }
    if depth != 0 {
        return None;
    }
    close(&mut parts, &mut part, n, n);
    Some(parts)
}

/// Where `footnote run -- ` goes in this part (the byte offset of the program that starts its pipeline) and the options
/// it needs, or `None` when the part runs nothing Footnote Lean filters, or its output goes somewhere a filter would
/// change.
fn part_rewrite_point(cmd: &str, part: &LinePart, shell: Shell) -> Option<(usize, RunFlags)> {
    if part.opaque || part.redirects_stdout {
        return None;
    }
    // Every later pipeline stage must only keep the first or last lines, which a filtered stream does not change.
    // Before `tail` or `-Last` the note line is left out, or it would take one of the last lines the agent asked for.
    let mut bounds = part.pipes.clone();
    bounds.push(part.end);
    let mut no_footer = false;
    for w in bounds.windows(2) {
        no_footer |= trims_lines(&cmd[w[0] + 1..w[1]])?;
    }
    let producer = &cmd[part.start..bounds[0]];
    let words = word_spans(producer)?;
    // `FOO=1 cargo test`: the assignments stay in front so the program still sees them. So do the bash keywords that
    // can start a part (`then cargo test`, `do git show $f`, `time cargo build`).
    let first = words.iter().position(|(_, w)| {
        !is_env_assignment(w)
            && !(shell == Shell::Posix
                && matches!(
                    w.as_str(),
                    "if" | "elif" | "then" | "else" | "do" | "while" | "until" | "time"
                ))
    })?;
    let argv: Vec<String> = words[first..]
        .iter()
        .map(|(_, w)| w.clone())
        .filter(|w| !w.starts_with("2>"))
        .collect();
    let bin = Path::new(argv.first()?)
        .file_stem()
        .and_then(|s| s.to_str())
        .unwrap_or("")
        .to_ascii_lowercase();
    if matches!(
        bin.as_str(),
        "footnote" | "rtk" | "env" | "printenv" | "set" | "export" | "ssh" | "vim" | "less"
    ) {
        return None;
    }
    if bin == "git" && git_waits_on_user(&argv) {
        return None;
    }
    // In PowerShell `ls` is `Get-ChildItem`; `footnote run` would start another program.
    if bin == "ls" && shell != Shell::Posix {
        return None;
    }
    if classify_command(&argv) == CommandFamily::Generic && !worth_wrapping(&argv) {
        return None;
    }
    Some((
        part.start + words[first].0,
        RunFlags {
            no_footer,
            raw_stderr: part.redirects_stderr,
        },
    ))
}

/// Whether a git command waits on the user: `-i`/`-p`/`-e` outside the commands where they shape output, or a commit
/// without a message, which opens an editor. `footnote run` shows output only once the program ends.
fn git_waits_on_user(argv: &[String]) -> bool {
    let Some(sub) = subcommand_of(argv) else {
        return false;
    };
    let sub = sub.to_ascii_lowercase();
    let after: Vec<&str> = argv[1..]
        .iter()
        .skip_while(|a| !a.eq_ignore_ascii_case(&sub))
        .skip(1)
        .map(String::as_str)
        .collect();
    let interactive = after.iter().any(|a| {
        matches!(
            *a,
            "-i" | "--interactive" | "-p" | "--patch" | "-e" | "--edit"
        )
    });
    match sub.as_str() {
        "log" | "show" | "diff" | "grep" | "blame" => false,
        "commit" => {
            interactive
                || !after.iter().any(|a| {
                    a.starts_with("--message")
                        || a.starts_with("--file")
                        || a.starts_with("--fixup")
                        || a.starts_with("--reuse-message")
                        || *a == "--no-edit"
                        || (a.starts_with('-')
                            && !a.starts_with("--")
                            && a.contains(['m', 'F', 'C']))
                })
        }
        _ => interactive,
    }
}

/// Whether a command keeps running or follows something: a dev server, a watcher, a followed log.
fn keeps_running(argv: &[String]) -> bool {
    argv[1..].iter().any(|a| {
        matches!(
            a.to_ascii_lowercase().as_str(),
            "dev"
                | "serve"
                | "start"
                | "preview"
                | "watch"
                | "--watch"
                | "-w"
                | "-f"
                | "--follow"
                | "--web"
                | "-it"
        )
    })
}

/// Commands outside the dedicated filters that still print enough to be worth the generic filter (long output is cut
/// to its head, tail and error lines, with the full text kept behind a handle). Everything else is left alone.
fn worth_wrapping(argv: &[String]) -> bool {
    const BUILD_WORDS: &[&str] = &[
        "build",
        "test",
        "lint",
        "check",
        "typecheck",
        "type-check",
        "deploy",
        "install",
        "add",
        "generate",
        "migrate",
        "publish",
        "format",
        "fmt",
        "audit",
        "ci",
    ];
    let bin = Path::new(&argv[0])
        .file_stem()
        .and_then(|s| s.to_str())
        .unwrap_or("")
        .to_ascii_lowercase();
    let sub = subcommand_of(argv).map(str::to_ascii_lowercase);
    if keeps_running(argv) {
        return false;
    }
    let names_build = || {
        argv[1..]
            .iter()
            .any(|a| BUILD_WORDS.contains(&a.to_ascii_lowercase().as_str()))
    };
    match bin.as_str() {
        "find" | "fd" | "tree" | "du" => true,
        "npx" | "pnpx" | "bunx" => names_build(),
        "npm" | "pnpm" | "yarn" | "bun" => match sub.as_deref() {
            Some(
                "ci" | "install" | "i" | "add" | "build" | "lint" | "audit" | "outdated" | "ls"
                | "list",
            ) => true,
            Some("run" | "run-script" | "exec" | "dlx" | "x") => names_build(),
            _ => false,
        },
        "cargo" => matches!(
            sub.as_deref(),
            Some("fmt" | "install" | "update" | "fetch" | "tree")
        ),
        "gh" => {
            !matches!(
                sub.as_deref(),
                Some("auth" | "browse" | "codespace" | "extension" | "alias" | "config")
            ) && !argv[1..]
                .iter()
                .any(|a| a == "-q" || a.starts_with("--jq") || a.starts_with("--template"))
        }
        "uv" => matches!(
            sub.as_deref(),
            Some("sync" | "lock" | "add" | "remove" | "pip")
        ),
        "pip" | "pip3" => matches!(sub.as_deref(), Some("install" | "list")),
        "make" | "mvn" | "mvnw" | "gradle" | "gradlew" => true,
        "dotnet" => matches!(
            sub.as_deref(),
            Some("build" | "test" | "restore" | "format")
        ),
        "go" => matches!(sub.as_deref(), Some("build" | "vet" | "mod")),
        "docker" => matches!(
            sub.as_deref(),
            Some("build" | "ps" | "images" | "logs" | "pull")
        ),
        "kubectl" => matches!(sub.as_deref(), Some("get" | "describe" | "logs")),
        _ => false,
    }
}

/// Whether a pipeline stage only keeps the first or last lines: `head`/`tail` with at most a line count, or PowerShell
/// `Select-Object -First/-Last N`. `Some(true)` when it keeps the last ones, `None` for any other stage.
fn trims_lines(stage: &str) -> Option<bool> {
    let words = split_simple_words(stage.trim())?;
    let count = |w: &str| !w.is_empty() && w.chars().all(|c| c.is_ascii_digit());
    match words[0].to_ascii_lowercase().as_str() {
        name @ ("head" | "tail") => words[1..]
            .iter()
            .all(|w| {
                w == "-n"
                    || count(w)
                    || w.strip_prefix("-n").is_some_and(count)
                    || w.strip_prefix('-').is_some_and(count)
                    || w.strip_prefix("--lines=").is_some_and(count)
            })
            .then_some(name == "tail"),
        "select-object" | "select" if words.len() == 3 && count(&words[2]) => {
            match words[1].to_ascii_lowercase().as_str() {
                "-first" => Some(false),
                "-last" => Some(true),
                _ => None,
            }
        }
        _ => None,
    }
}

fn is_env_assignment(word: &str) -> bool {
    word.split_once('=').is_some_and(|(name, _)| {
        !name.is_empty()
            && !name.starts_with(|c: char| c.is_ascii_digit())
            && name.chars().all(|c| c.is_ascii_alphanumeric() || c == '_')
    })
}

/// Words of a simple command with the byte offset where each starts (quotes removed from the value).
fn word_spans(s: &str) -> Option<Vec<(usize, String)>> {
    let mut words = Vec::new();
    let mut cur = String::new();
    let mut start = None;
    let mut quote: Option<char> = None;
    for (i, c) in s.char_indices() {
        match (quote, c) {
            (Some(q), ch) if ch == q => quote = None,
            (Some(_), ch) => cur.push(ch),
            (None, '\'' | '"') => {
                start.get_or_insert(i);
                quote = Some(c);
            }
            (None, ch) if ch.is_whitespace() => {
                if let Some(at) = start.take() {
                    words.push((at, std::mem::take(&mut cur)));
                }
            }
            (None, ch) => {
                start.get_or_insert(i);
                cur.push(ch);
            }
        }
    }
    if quote.is_some() {
        return None;
    }
    if let Some(at) = start {
        words.push((at, cur));
    }
    (!words.is_empty()).then_some(words)
}

fn split_simple_words(s: &str) -> Option<Vec<String>> {
    let mut words = Vec::new();
    let mut cur = String::new();
    let mut quote: Option<char> = None;
    for c in s.chars() {
        match (quote, c) {
            (Some(q), ch) if ch == q => quote = None,
            (Some(_), ch) => cur.push(ch),
            (None, '\'' | '"') => quote = Some(c),
            (None, ch) if ch.is_whitespace() => {
                if !cur.is_empty() {
                    words.push(std::mem::take(&mut cur));
                }
            }
            (None, ch) => cur.push(ch),
        }
    }
    if quote.is_some() {
        return None;
    }
    if !cur.is_empty() {
        words.push(cur);
    }
    (!words.is_empty()).then_some(words)
}

/// Fail-closed detector for secrets/credentials. Any match prevents persisting raw output to disk.
#[must_use]
pub fn contains_secrets(text: &str) -> bool {
    static PATTERNS: OnceLock<Vec<Regex>> = OnceLock::new();
    let regexes = PATTERNS.get_or_init(|| {
        [
            r"-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----",
            r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b",
            r"\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{20,}\b",
            r"\bgithub_pat_[A-Za-z0-9_]{20,}\b",
            r"\bsk-(?:ant-|proj-|live-|test-)?[A-Za-z0-9_-]{20,}\b",
            r"(?i)\bAuthorization\s*:\s*(?:Bearer|Basic)\s+[A-Za-z0-9._~+/=-]{8,}",
            r"[a-zA-Z][a-zA-Z0-9+.-]*://[^/\s:@]{1,64}:[^/\s@]{6,}@[^\s/]+",
            r"(?i)\b(?:password|passwd|secret|api[_-]?key|access[_-]?token|private[_-]?key|client[_-]?secret|auth[_-]?token)\s*[:=]\s*['\x22]?[A-Za-z0-9_/+.-]{8,}",
            r"\beyJ[A-Za-z0-9_-]{10,}\.eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b",
        ]
        .iter()
        .filter_map(|p| Regex::new(p).ok())
        .collect()
    });
    regexes.iter().any(|rx| rx.is_match(text))
}

#[derive(Debug, Clone)]
pub struct RunOptions {
    pub raw: bool,
    pub no_store: bool,
    pub stdin_mode: bool,
    pub rewrite: Option<String>,
    pub family_override: Option<CommandFamily>,
    /// Leave out the closing `[footnote: …]` line: the hook sets it when the output is piped into `tail`.
    pub no_footer: bool,
    /// Leave the program's stderr on Footnote's stderr instead of merging it into the filtered output: the hook sets it
    /// when the agent sent stderr elsewhere (`2>/dev/null`, `2>err.txt`).
    pub raw_stderr: bool,
    pub command: Vec<String>,
}

/// Execute `footnote run` directly, writing filtered (or raw) output to stdout and exiting with the child's exit code.
pub fn run_cli(opts: &RunOptions) -> i32 {
    if let Some(cmd) = &opts.rewrite {
        if let Some(rewritten) = rewrite_command(cmd) {
            println!("{rewritten}");
            return 0;
        }
        return 1;
    }
    match run_inner(opts) {
        Ok(code) => code,
        Err(e) => {
            eprintln!("footnote run: {e:#}");
            1
        }
    }
}

fn run_inner(opts: &RunOptions) -> Result<i32> {
    let cwd = std::env::current_dir().unwrap_or_else(|_| PathBuf::from("."));
    let (raw_output, exit_code, family) = if opts.stdin_mode {
        let mut input = std::io::stdin().lock();
        let mut bytes = Vec::new();
        input
            .by_ref()
            .take(MAX_STORE_BYTES as u64 + 1)
            .read_to_end(&mut bytes)?;
        if bytes.len() > MAX_STORE_BYTES {
            let mut output = std::io::stdout().lock();
            output.write_all(&bytes)?;
            std::io::copy(&mut input, &mut output)?;
            return Ok(0);
        }
        let buf = String::from_utf8(bytes).context("read stdin")?;
        let fam = opts.family_override.unwrap_or(CommandFamily::Generic);
        (buf, 0, fam)
    } else {
        if opts.command.is_empty() {
            bail!("expected a command after `--` (e.g. `footnote run -- cargo test`)");
        }
        let fam = opts
            .family_override
            .unwrap_or_else(|| classify_command(&opts.command));
        let (combined, code) = spawn_and_capture(&opts.command, opts.raw_stderr)?;
        let Some(output) = combined else {
            return Ok(code);
        };
        (output, code, fam)
    };

    if opts.raw || raw_output.is_empty() {
        let mut stdout = std::io::stdout().lock();
        let _ = stdout.write_all(raw_output.as_bytes());
        let _ = stdout.flush();
        return Ok(exit_code);
    }

    let raw_bytes = raw_output.len();
    let has_secrets = contains_secrets(&raw_output);
    // `ls -t`, `ls -lt`, `--time-style`, `--full-time`: the listing is about dates, so the filter keeps them.
    let shows_time = family == CommandFamily::Listing
        && opts.command[1..].iter().any(|a| {
            a.starts_with("--time")
                || a == "--full-time"
                || (a.starts_with('-') && !a.starts_with("--") && a.contains('t'))
        });
    let family_sub = if family == CommandFamily::Listing {
        shows_time.then_some("time")
    } else {
        subcommand_of(&opts.command)
    };

    // Track whether uniform JSON-array compaction fired so `footnote gain` attributes it cleanly (#381).
    let (effective_family, filtered_body) =
        std::panic::catch_unwind(std::panic::AssertUnwindSafe(|| {
            if matches!(family, CommandFamily::Generic | CommandFamily::JsonArray)
                && !has_secrets
                && let Some(compact) = filter_json_array(&raw_output)
            {
                return (CommandFamily::JsonArray, compact);
            }
            (family, filter_output(family, family_sub, &raw_output))
        }))
        .unwrap_or_else(|_| (family, raw_output.clone()));

    let repeat_eligible = !opts.stdin_mode
        && !opts.command.is_empty()
        && !has_secrets
        && !opts.no_store
        && matches!(
            effective_family,
            CommandFamily::CargoTest
                | CommandFamily::CargoBuild
                | CommandFamily::TestRunner
                | CommandFamily::Linter
        );

    if repeat_eligible && exit_code == 0 {
        clear_repeat_entry(&cwd, &opts.command);
    }

    // Consecutive identical failing run delta (#381): collapse repeat diagnostics to 3 lines referencing prior handle.
    let fail_sig = if repeat_eligible && exit_code != 0 {
        let sig = failure_signature(&filtered_body);
        if let Some((prior_handle, count)) =
            check_and_bump_repeat(&cwd, &opts.command, &sig, exit_code)
            && let Some(repeat_out) = format_repeat_delta(
                effective_family,
                &opts.command,
                exit_code,
                count,
                &filtered_body,
                raw_bytes,
                &prior_handle,
            )
            && repeat_out.len() < raw_bytes
        {
            let mut stdout = std::io::stdout().lock();
            let _ = stdout.write_all(repeat_out.as_bytes());
            let _ = stdout.flush();
            log_lean_run(
                effective_family,
                raw_bytes,
                repeat_out.len(),
                None,
                exit_code,
            );
            return Ok(exit_code);
        }
        Some(sig)
    } else {
        None
    };

    if filtered_body.len() >= raw_bytes {
        // On a failing diagnostic run that passed through raw, quietly keep a handle so an identical retry
        // can emit a 3-line repeat delta without losing access to the full diagnostic (#381).
        if let Some(sig) = fail_sig
            && (512..=MAX_STORE_BYTES).contains(&raw_bytes)
            && let Ok(id) = store_raw_output(&raw_output)
        {
            record_repeat_entry(&cwd, &opts.command, sig, id, exit_code, raw_bytes);
        }
        let mut stdout = std::io::stdout().lock();
        let _ = stdout.write_all(raw_output.as_bytes());
        let _ = stdout.flush();
        log_lean_run(effective_family, raw_bytes, raw_bytes, None, exit_code);
        return Ok(exit_code);
    }

    #[cfg(feature = "code")]
    let code_links = if exit_code != 0 || has_error_markers(&filtered_body) {
        resolve_code_links(&cwd, &filtered_body)
    } else {
        String::new()
    };
    #[cfg(not(feature = "code"))]
    let code_links = {
        let _ = &cwd;
        String::new()
    };

    let candidate_without_footer = if code_links.is_empty() {
        filtered_body
    } else {
        format!("{}\n{code_links}", filtered_body.trim_end())
    };

    // Estimate footer length before deciding whether to persist a handle.
    let provisional_footer = if opts.no_footer {
        "\n".to_string()
    } else if has_secrets {
        format!(
            "\n[footnote: {} {}B -> {}B | full output not stored: potential credentials detected]\n",
            effective_family.as_str(),
            raw_bytes,
            candidate_without_footer.len()
        )
    } else if opts.no_store || raw_bytes > MAX_STORE_BYTES {
        format!(
            "\n[footnote: {} {}B -> {}B | full output not stored]\n",
            effective_family.as_str(),
            raw_bytes,
            candidate_without_footer.len()
        )
    } else {
        format!(
            "\n[footnote: {} {}B -> {}B (-99%) | full: footnote output h-000000000000 [--grep pat]]\n",
            effective_family.as_str(),
            raw_bytes,
            candidate_without_footer.len()
        )
    };

    if candidate_without_footer.len() + provisional_footer.len() >= raw_bytes {
        if let Some(sig) = fail_sig
            && (512..=MAX_STORE_BYTES).contains(&raw_bytes)
            && let Ok(id) = store_raw_output(&raw_output)
        {
            record_repeat_entry(&cwd, &opts.command, sig, id, exit_code, raw_bytes);
        }
        let mut stdout = std::io::stdout().lock();
        let _ = stdout.write_all(raw_output.as_bytes());
        let _ = stdout.flush();
        log_lean_run(effective_family, raw_bytes, raw_bytes, None, exit_code);
        return Ok(exit_code);
    }

    // Only write handle after confirming shortening saves bytes and output is credential-free.
    let handle_id = if !has_secrets && !opts.no_store && raw_bytes <= MAX_STORE_BYTES {
        store_raw_output(&raw_output).ok()
    } else {
        None
    };

    let body_trimmed = candidate_without_footer.trim_end();
    let pct = 100usize.saturating_sub(
        (body_trimmed.len().saturating_mul(100))
            .checked_div(raw_bytes)
            .unwrap_or(100),
    );
    let footer = match &handle_id {
        _ if opts.no_footer => "\n".to_string(),
        Some(id) => format!(
            "\n[footnote: {} {}B -> {}B (-{}%) | full: footnote output {} [--grep pat]]\n",
            effective_family.as_str(),
            raw_bytes,
            body_trimmed.len(),
            pct,
            id
        ),
        None if has_secrets => format!(
            "\n[footnote: {} {}B -> {}B (-{}%) | full output not stored: potential credentials detected]\n",
            effective_family.as_str(),
            raw_bytes,
            body_trimmed.len(),
            pct
        ),
        None => format!(
            "\n[footnote: {} {}B -> {}B (-{}%)]\n",
            effective_family.as_str(),
            raw_bytes,
            body_trimmed.len(),
            pct
        ),
    };

    let final_out = format!("{body_trimmed}{footer}");
    if final_out.len() >= raw_bytes {
        if let Some(id) = &handle_id {
            remove_handle(id);
        }
        let mut stdout = std::io::stdout().lock();
        let _ = stdout.write_all(raw_output.as_bytes());
        let _ = stdout.flush();
        log_lean_run(effective_family, raw_bytes, raw_bytes, None, exit_code);
        return Ok(exit_code);
    }

    if let (Some(sig), Some(id)) = (fail_sig, &handle_id) {
        record_repeat_entry(&cwd, &opts.command, sig, id.clone(), exit_code, raw_bytes);
    }

    let mut stdout = std::io::stdout().lock();
    let _ = stdout.write_all(final_out.as_bytes());
    let _ = stdout.flush();
    log_lean_run(
        effective_family,
        raw_bytes,
        final_out.len(),
        handle_id.as_deref(),
        exit_code,
    );
    Ok(exit_code)
}

/// The program `name` names, found the way the agent's shell finds it. On Windows `Command::new` looks in the system
/// folders before `PATH` and tries only `.exe`, so `find` would start `C:\Windows\System32\find.exe` instead of the
/// `find` the shell runs, and `npx`, `npm` and other `.cmd` shims would not start at all.
fn resolve_program(name: &str) -> std::ffi::OsString {
    #[cfg(windows)]
    if !name.contains(['/', '\\', ':']) {
        let pathext = std::env::var("PATHEXT").unwrap_or_else(|_| ".COM;.EXE;.BAT;.CMD".into());
        let exts: Vec<String> = pathext
            .split(';')
            .map(str::to_ascii_lowercase)
            .filter(|e| matches!(e.as_str(), ".com" | ".exe" | ".bat" | ".cmd"))
            .collect();
        let has_ext = Path::new(name)
            .extension()
            .and_then(|e| e.to_str())
            .is_some_and(|e| exts.iter().any(|x| x[1..].eq_ignore_ascii_case(e)));
        for dir in std::env::split_paths(&std::env::var_os("PATH").unwrap_or_default()) {
            if has_ext {
                if dir.join(name).is_file() {
                    return dir.join(name).into_os_string();
                }
                continue;
            }
            for ext in &exts {
                let p = dir.join(format!("{name}{ext}"));
                if p.is_file() {
                    return p.into_os_string();
                }
            }
        }
    }
    name.into()
}

fn spawn_and_capture(cmd: &[String], raw_stderr: bool) -> Result<(Option<String>, i32)> {
    let mut child = Command::new(resolve_program(&cmd[0]))
        .args(&cmd[1..])
        .stdin(Stdio::inherit())
        .stdout(Stdio::piped())
        .stderr(if raw_stderr {
            Stdio::inherit()
        } else {
            Stdio::piped()
        })
        .spawn()
        .with_context(|| format!("failed to spawn `{}`", cmd[0]))?;

    let out = child.stdout.take().context("child stdout")?;
    let err = child.stderr.take();
    // Drain both pipes concurrently. Once the combined budget is exceeded, bypass
    // compaction and forward bytes as they arrive without persisting raw output.
    let (sender, receiver) = std::sync::mpsc::sync_channel(4);
    let pump = |mut pipe: Box<dyn Read + Send>,
                stderr,
                tx: std::sync::mpsc::SyncSender<(bool, Vec<u8>)>| {
        std::thread::spawn(move || -> std::io::Result<()> {
            let mut buf = [0u8; 32 * 1024];
            loop {
                let n = match pipe.read(&mut buf) {
                    Err(e) if e.kind() == std::io::ErrorKind::Interrupted => continue,
                    result => result?,
                };
                if n == 0 || tx.send((stderr, buf[..n].to_vec())).is_err() {
                    break;
                }
            }
            Ok(())
        })
    };
    let err_reader = err.map(|err| pump(Box::new(err), true, sender.clone()));
    let out_reader = pump(Box::new(out), false, sender);
    let (mut stdout_bytes, mut stderr_bytes) = (Vec::new(), Vec::new());
    let mut streaming = false;
    let mut output = std::io::stdout().lock();
    let drained = (|| -> std::io::Result<()> {
        for (stderr, chunk) in receiver {
            if !streaming && stdout_bytes.len() + stderr_bytes.len() + chunk.len() > MAX_STORE_BYTES
            {
                streaming = true;
                output.write_all(&stderr_bytes)?;
                output.write_all(&stdout_bytes)?;
                stdout_bytes.clear();
                stderr_bytes.clear();
            }
            if streaming {
                output.write_all(&chunk)?;
            } else if stderr {
                stderr_bytes.extend_from_slice(&chunk);
            } else {
                stdout_bytes.extend_from_slice(&chunk);
            }
        }
        Ok(())
    })();
    if drained.is_err() {
        let _ = child.kill();
    }
    let exit_code = child
        .wait()
        .context("wait for child process")?
        .code()
        .unwrap_or(1);
    out_reader
        .join()
        .map_err(|_| anyhow::anyhow!("stdout reader failed"))??;
    if let Some(err_reader) = err_reader {
        err_reader
            .join()
            .map_err(|_| anyhow::anyhow!("stderr reader failed"))??;
    }
    drained?;
    if streaming {
        return Ok((None, exit_code));
    }

    let stdout_str = String::from_utf8_lossy(&stdout_bytes);
    let stderr_str = String::from_utf8_lossy(&stderr_bytes);

    let combined = match (stdout_str.is_empty(), stderr_str.is_empty()) {
        (true, true) => String::new(),
        (false, true) => stdout_str.into_owned(),
        (true, false) => stderr_str.into_owned(),
        (false, false) => {
            if stderr_str.ends_with('\n') {
                format!("{stderr_str}{stdout_str}")
            } else {
                format!("{stderr_str}\n{stdout_str}")
            }
        }
    };
    Ok((Some(combined), exit_code))
}

/// Core preservation-first dispatcher across the shipped command families.
#[must_use]
pub fn filter_output(family: CommandFamily, subcommand: Option<&str>, raw: &str) -> String {
    match family {
        CommandFamily::CargoTest => filter_cargo_test(raw),
        CommandFamily::CargoBuild => filter_cargo_build(raw),
        CommandFamily::TestRunner => filter_test_runner(raw),
        CommandFamily::Git => filter_git(subcommand, raw),
        CommandFamily::Search => filter_search(raw),
        CommandFamily::Linter => filter_linter(raw),
        CommandFamily::JsonArray => filter_json_array(raw).unwrap_or_else(|| filter_generic(raw)),
        CommandFamily::Listing => filter_listing(raw, subcommand == Some("time")),
        CommandFamily::Generic => filter_json_array(raw).unwrap_or_else(|| filter_generic(raw)),
    }
}

/// `ls -l` keeps each entry's name, size and kind (`dir/`, `tool*` for an executable, `link -> target`) and drops the
/// permission, link-count, owner and group columns, and the date unless the listing is sorted or shown by time
/// (`subcommand` is `"time"` then). `.` and `..` and the `total` line go; other lines (plain `ls`, `dir:` headers of
/// `ls -R`) pass through.
fn filter_listing(raw: &str, keep_time: bool) -> String {
    let mut out = String::with_capacity(raw.len() / 2);
    for line in raw.lines() {
        if line.strip_prefix("total ").is_some_and(|n| {
            n.trim()
                .chars()
                .all(|c| c.is_ascii_alphanumeric() || c == '.')
        }) {
            continue;
        }
        match long_listing_entry(line, keep_time) {
            Some(None) => continue,
            Some(Some(entry)) => out.push_str(&entry),
            None => out.push_str(line),
        }
        out.push('\n');
    }
    out
}

/// One `ls -l` line made short: `None` when the line is not a long-format entry, `Some(None)` for `.` and `..`.
fn long_listing_entry(line: &str, keep_time: bool) -> Option<Option<String>> {
    let mut tokens: Vec<(usize, &str)> = Vec::with_capacity(9);
    let mut rest = line;
    let mut offset = 0;
    while tokens.len() < 9 {
        let trimmed = rest.trim_start();
        if trimmed.is_empty() {
            break;
        }
        let start = offset + (rest.len() - trimmed.len());
        let len = trimmed.find(char::is_whitespace).unwrap_or(trimmed.len());
        tokens.push((start, &trimmed[..len]));
        offset = start + len;
        rest = &line[offset..];
    }
    let perms = tokens.first()?.1.as_bytes();
    let kinds = b"-dlcbps";
    if !(10..=11).contains(&perms.len())
        || !kinds.contains(&perms[0])
        || !perms[1..10].iter().all(|c| b"rwxsStT-".contains(c))
    {
        return None;
    }
    let digits = |t: &str| !t.is_empty() && t.bytes().all(|c| c.is_ascii_digit());
    if tokens.len() < 8 || !digits(tokens[1].1) || !digits(tokens[4].1) {
        return None;
    }
    let size: u64 = tokens[4].1.parse().ok()?;
    // `2026-11-23 10:31[:00.000] [+0100]` (`--time-style`) or `Nov 23 10:31` / `Nov 23  2025`.
    let date_end = if tokens[5].1.len() == 10 && tokens[5].1.as_bytes()[4] == b'-' {
        let mut end = 6;
        if tokens.get(end).is_some_and(|t| t.1.contains(':')) {
            end += 1;
        }
        if tokens
            .get(end)
            .is_some_and(|t| t.1.len() == 5 && matches!(t.1.as_bytes()[0], b'+' | b'-'))
        {
            end += 1;
        }
        end
    } else if tokens[5].1.len() == 3
        && tokens[5].1.bytes().all(|c| c.is_ascii_alphabetic())
        && digits(tokens[6].1)
    {
        8
    } else {
        return None;
    };
    let name_at = tokens.get(date_end)?.0;
    let name = &line[name_at..];
    if name == "." || name == ".." || name == "./" || name == "../" {
        return Some(None);
    }
    let mut entry = String::new();
    if keep_time {
        entry.push_str(&line[tokens[5].0..tokens[date_end - 1].0 + tokens[date_end - 1].1.len()]);
        entry.push_str("  ");
    }
    entry.push_str(name);
    match perms[0] {
        b'd' if !name.ends_with('/') => entry.push('/'),
        b'd' | b'l' => {}
        _ => {
            if [perms[3], perms[6], perms[9]]
                .iter()
                .any(|c| matches!(c, b'x' | b's' | b't'))
            {
                entry.push('*');
            }
            entry.push_str("  ");
            entry.push_str(&human_size(size));
        }
    }
    Some(Some(entry))
}

fn human_size(bytes: u64) -> String {
    #[allow(clippy::cast_precision_loss)]
    let b = bytes as f64;
    match bytes {
        0..1024 => format!("{bytes}"),
        1024..1_048_576 => format!("{:.1}K", b / 1024.0),
        1_048_576..1_073_741_824 => format!("{:.1}M", b / 1_048_576.0),
        _ => format!("{:.1}G", b / 1_073_741_824.0),
    }
}

/// Compact a uniform JSON array of >= 8 objects (> 2 KB) with zero detected secrets into a schema-preserving
/// summary + key distributions + sample rows (#381). Returns `None` if criteria do not match.
#[must_use]
pub fn filter_json_array(raw: &str) -> Option<String> {
    if raw.len() <= JSON_ARRAY_MIN_BYTES || contains_secrets(raw) {
        return None;
    }
    let trimmed = raw.trim();
    if !trimmed.starts_with('[') || !trimmed.ends_with(']') {
        return None;
    }
    let Value::Array(items) = serde_json::from_str::<Value>(trimmed).ok()? else {
        return None;
    };
    if items.len() < JSON_ARRAY_MIN_ITEMS {
        return None;
    }
    let objs: Vec<&serde_json::Map<String, Value>> = items
        .iter()
        .map(Value::as_object)
        .collect::<Option<Vec<_>>>()?;
    if objs.iter().any(|o| o.is_empty()) {
        return None;
    }

    // Check schema uniformity: keys present in >= 50% of items form the core schema; every item must have
    // >= 60% of its keys in that core set.
    let mut key_counts: BTreeMap<&str, usize> = BTreeMap::new();
    for obj in &objs {
        for k in obj.keys() {
            *key_counts.entry(k.as_str()).or_default() += 1;
        }
    }
    let min_common = objs.len().div_ceil(2);
    let core_keys: std::collections::HashSet<&str> = key_counts
        .iter()
        .filter(|(_, c)| **c >= min_common)
        .map(|(k, _)| *k)
        .collect();
    if core_keys.is_empty() {
        return None;
    }
    for obj in &objs {
        let shared = obj
            .keys()
            .filter(|k| core_keys.contains(k.as_str()))
            .count();
        if shared * 5 < obj.len() * 3 {
            return None;
        }
    }

    const PRIORITY_KEYS: &[&str] = &[
        "number", "id", "key", "name", "title", "state", "status", "kind", "type", "url",
    ];
    let mut ordered_keys: Vec<&str> = Vec::with_capacity(key_counts.len());
    for &pk in PRIORITY_KEYS {
        if key_counts.contains_key(pk) {
            ordered_keys.push(pk);
        }
    }
    for &k in key_counts.keys() {
        if !ordered_keys.contains(&k) {
            ordered_keys.push(k);
        }
    }

    let listed_keys = if ordered_keys.len() > 12 {
        format!(
            "{}, +{} more",
            ordered_keys[..12].join(", "),
            ordered_keys.len() - 12
        )
    } else {
        ordered_keys.join(", ")
    };

    let mut out = Vec::new();
    out.push(format!(
        "json array: {} items, {} keys ({listed_keys})",
        objs.len(),
        ordered_keys.len()
    ));

    // Summarize low-cardinality categorical fields (e.g. `state: OPEN=12, CLOSED=3`).
    let mut dists = Vec::new();
    for &field in &["state", "status", "kind", "type", "conclusion"] {
        if !key_counts.contains_key(field) {
            continue;
        }
        let mut counts: BTreeMap<&str, usize> = BTreeMap::new();
        for obj in &objs {
            if let Some(s) = obj.get(field).and_then(Value::as_str) {
                *counts.entry(s).or_default() += 1;
            }
        }
        if !counts.is_empty() && counts.len() <= 6 {
            let parts: Vec<String> = counts
                .into_iter()
                .map(|(k, c)| format!("{k}={c}"))
                .collect();
            dists.push(format!("{field}: {}", parts.join(", ")));
        }
    }
    if !dists.is_empty() {
        out.push(format!("summary: {}", dists.join(" | ")));
    }

    // Pick up to 4 most informative non-blob keys for compact one-line sample rows.
    let display_keys: Vec<&str> = ordered_keys
        .iter()
        .copied()
        .filter(|k| !matches!(*k, "body" | "description" | "content" | "diff" | "raw"))
        .take(4)
        .collect();
    let display_keys = if display_keys.is_empty() {
        ordered_keys.iter().copied().take(3).collect()
    } else {
        display_keys
    };

    let format_row = |idx: usize, obj: &serde_json::Map<String, Value>| -> String {
        let mut parts = Vec::new();
        for &k in &display_keys {
            if let Some(v) = obj.get(k) {
                let rendered = compact_json_val(v);
                if !rendered.is_empty() {
                    parts.push(format!("{k}={rendered}"));
                }
            }
        }
        format!("  [{idx}] {}", parts.join(" "))
    };

    let head = 3usize.min(objs.len());
    for (i, obj) in objs.iter().take(head).enumerate() {
        out.push(format_row(i, obj));
    }
    if objs.len() > 5 {
        out.push(format!("  ... {} more items ...", objs.len() - 5));
        let start = objs.len() - 2;
        for (offset, obj) in objs[start..].iter().enumerate() {
            out.push(format_row(start + offset, obj));
        }
    } else if objs.len() > head {
        for (offset, obj) in objs[head..].iter().enumerate() {
            out.push(format_row(head + offset, obj));
        }
    }

    let rendered = out.join("\n");
    (rendered.len() < raw.len()).then_some(rendered)
}

fn compact_json_val(v: &Value) -> String {
    match v {
        Value::Null => String::new(),
        Value::Bool(b) => b.to_string(),
        Value::Number(n) => n.to_string(),
        Value::String(s) => {
            let one_line: String = s.split_whitespace().collect::<Vec<_>>().join(" ");
            if one_line.chars().count() > 64 {
                let cut: String = one_line.chars().take(61).collect();
                format!("\"{cut}...\"")
            } else {
                format!("\"{one_line}\"")
            }
        }
        Value::Array(arr) => {
            if arr.is_empty() {
                "[]".into()
            } else {
                let names: Vec<&str> = arr
                    .iter()
                    .take(3)
                    .filter_map(|it| {
                        it.as_str()
                            .or_else(|| it.get("name").and_then(Value::as_str))
                            .or_else(|| it.get("login").and_then(Value::as_str))
                    })
                    .collect();
                if names.is_empty() {
                    format!("[{} items]", arr.len())
                } else if arr.len() > 3 {
                    format!("[{}, +{}]", names.join(","), arr.len() - 3)
                } else {
                    format!("[{}]", names.join(","))
                }
            }
        }
        Value::Object(map) => {
            for k in ["login", "name", "id", "title"] {
                if let Some(s) = map.get(k).and_then(Value::as_str) {
                    return s.to_string();
                }
            }
            format!("{{{} keys}}", map.len())
        }
    }
}

#[derive(serde::Serialize, serde::Deserialize)]
struct RepeatEntry {
    sig: String,
    handle: String,
    exit_code: i32,
    raw_bytes: usize,
    count: u32,
    updated_at_secs: u64,
}

fn now_secs() -> u64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap_or_default()
        .as_secs()
}

fn repeat_state_path() -> Result<PathBuf> {
    let dir = crate::state::state_dir()?.join("usage");
    crate::state::ensure_private_dir(&dir)?;
    Ok(dir.join("repeat-runs.json"))
}

fn repeat_key(cwd: &Path, cmd: &[String]) -> String {
    let joined = format!("{}|{}", cwd.to_string_lossy(), cmd.join("\0"));
    footnote_core::hash(joined.as_bytes())[..16].to_string()
}

/// Normalize timing/address jitter out of failing diagnostics while keeping every error, path, line number,
/// and assertion value intact (#381).
fn failure_signature(filtered: &str) -> String {
    static TIME_RE: OnceLock<Option<Regex>> = OnceLock::new();
    static HEX_RE: OnceLock<Option<Regex>> = OnceLock::new();
    let time_re = TIME_RE
        .get_or_init(|| Regex::new(r"\b\d+(?:\.\d+)?\s*(?:ms|s)\b").ok())
        .as_ref();
    let hex_re = HEX_RE
        .get_or_init(|| Regex::new(r"\b0x[0-9a-fA-F]{6,}\b").ok())
        .as_ref();

    let clean = strip_ansi(filtered);
    let mut norm = String::new();
    for line in clean.lines() {
        let t = line.trim();
        if t.is_empty() {
            continue;
        }
        let s = match time_re {
            Some(re) => re.replace_all(t, "<T>").into_owned(),
            None => t.to_string(),
        };
        let s = match hex_re {
            Some(re) => re.replace_all(&s, "<HEX>").into_owned(),
            None => s,
        };
        norm.push_str(&s);
        norm.push('\n');
    }
    footnote_core::hash(norm.as_bytes())[..24].to_string()
}

fn load_repeat_state(path: &Path) -> BTreeMap<String, RepeatEntry> {
    fs::read_to_string(path)
        .ok()
        .and_then(|s| serde_json::from_str(&s).ok())
        .unwrap_or_default()
}

fn save_repeat_state(path: &Path, mut map: BTreeMap<String, RepeatEntry>) {
    let now = now_secs();
    map.retain(|_, v| now.saturating_sub(v.updated_at_secs) <= REPEAT_WINDOW_SECS);
    if map.len() > MAX_REPEAT_ENTRIES {
        let mut by_age: Vec<(u64, String)> = map
            .iter()
            .map(|(k, v)| (v.updated_at_secs, k.clone()))
            .collect();
        by_age.sort_by_key(|(t, _)| *t);
        for (_, old_k) in by_age.into_iter().take(map.len() - MAX_REPEAT_ENTRIES) {
            map.remove(&old_k);
        }
    }
    let tmp = path.with_extension("json.tmp");
    if let Ok(bytes) = serde_json::to_vec(&map)
        && fs::write(&tmp, bytes).is_ok()
    {
        let _ = fs::rename(&tmp, path);
    }
}

fn clear_repeat_entry(cwd: &Path, cmd: &[String]) {
    let Ok(path) = repeat_state_path() else {
        return;
    };
    if !path.is_file() {
        return;
    }
    let mut map = load_repeat_state(&path);
    if map.remove(&repeat_key(cwd, cmd)).is_some() {
        save_repeat_state(&path, map);
    }
}

fn check_and_bump_repeat(
    cwd: &Path,
    cmd: &[String],
    sig: &str,
    exit_code: i32,
) -> Option<(String, u32)> {
    let path = repeat_state_path().ok()?;
    let mut map = load_repeat_state(&path);
    let key = repeat_key(cwd, cmd);
    let now = now_secs();
    let entry = map.get_mut(&key)?;
    if now.saturating_sub(entry.updated_at_secs) > REPEAT_WINDOW_SECS
        || entry.sig != sig
        || entry.exit_code != exit_code
    {
        return None;
    }
    let handle_file = outputs_dir().ok()?.join(format!("{}.txt", entry.handle));
    if !handle_file.is_file() {
        return None;
    }
    entry.count = entry.count.saturating_add(1);
    entry.updated_at_secs = now;
    let res = (entry.handle.clone(), entry.count);
    save_repeat_state(&path, map);
    Some(res)
}

fn record_repeat_entry(
    cwd: &Path,
    cmd: &[String],
    sig: String,
    handle: String,
    exit_code: i32,
    raw_bytes: usize,
) {
    let Ok(path) = repeat_state_path() else {
        return;
    };
    let mut map = load_repeat_state(&path);
    map.insert(
        repeat_key(cwd, cmd),
        RepeatEntry {
            sig,
            handle,
            exit_code,
            raw_bytes,
            count: 1,
            updated_at_secs: now_secs(),
        },
    );
    save_repeat_state(&path, map);
}

fn format_repeat_delta(
    family: CommandFamily,
    cmd: &[String],
    exit_code: i32,
    count: u32,
    filtered: &str,
    raw_bytes: usize,
    prior_handle: &str,
) -> Option<String> {
    let cmd_preview: String = cmd.join(" ").chars().take(72).collect();
    let diag_lines = filtered.lines().filter(|l| !l.trim().is_empty()).count();
    let first_marker = filtered
        .lines()
        .find(|l| is_important_line(l))
        .or_else(|| filtered.lines().find(|l| !l.trim().is_empty()))
        .unwrap_or("identical failure")
        .trim();
    let first_marker: String = first_marker.chars().take(100).collect();
    let line1 =
        format!("repeat failure (#{count} identical in session, exit {exit_code}): {cmd_preview}");
    let line2 = format!("same diagnostic ({diag_lines} lines) — {first_marker}");
    let body_len = line1.len() + 1 + line2.len();
    let pct = 100usize.saturating_sub(
        (body_len.saturating_mul(100))
            .checked_div(raw_bytes)
            .unwrap_or(100),
    );
    let line3 = format!(
        "[footnote: {} repeat-delta {}B -> {}B (-{}%) | prior full: footnote output {} [--grep pat]]",
        family.as_str(),
        raw_bytes,
        body_len,
        pct,
        prior_handle
    );
    Some(format!("{line1}\n{line2}\n{line3}\n"))
}

fn strip_ansi(s: &str) -> String {
    static ANSI_RE: OnceLock<Option<Regex>> = OnceLock::new();
    let Some(rx) = ANSI_RE
        .get_or_init(|| Regex::new(r"\x1b\[[0-9;]*[A-Za-z]").ok())
        .as_ref()
    else {
        return s.to_string();
    };
    rx.replace_all(s, "").into_owned()
}

fn is_cargo_progress_line(trimmed: &str) -> bool {
    const PREFIXES: &[&str] = &[
        "Compiling ",
        "Checking ",
        "Downloading ",
        "Downloaded ",
        "Updating ",
        "Locking ",
        "Fresh ",
        "Documenting ",
        "Blocking waiting for file lock",
        "Packaging ",
        "Archiving ",
    ];
    PREFIXES.iter().any(|p| trimmed.starts_with(p))
}

fn is_rustc_diag_start(trimmed: &str) -> bool {
    trimmed.starts_with("error[")
        || trimmed.starts_with("error:")
        || trimmed.starts_with("warning:")
        || trimmed.starts_with("warning[")
}

fn is_rustc_diag_continuation(line: &str, trimmed: &str) -> bool {
    trimmed.starts_with("--> ")
        || trimmed.starts_with("|")
        || trimmed.starts_with("= ")
        || trimmed.starts_with("note:")
        || trimmed.starts_with("help:")
        || trimmed.starts_with("...")
        || line
            .bytes()
            .take_while(|b| b.is_ascii_whitespace() || b.is_ascii_digit())
            .count()
            > 0
            && line.contains(" | ")
        || line.trim_start().starts_with("| ")
}

fn filter_cargo_build(raw: &str) -> String {
    let clean = strip_ansi(raw);
    let mut kept = Vec::new();
    let mut compiled = 0usize;
    let mut in_diag = false;

    for line in clean.lines() {
        let trimmed = line.trim();
        if trimmed.is_empty() {
            if in_diag {
                kept.push(String::new());
                in_diag = false;
            }
            continue;
        }
        if is_cargo_progress_line(trimmed) {
            if trimmed.starts_with("Compiling ") || trimmed.starts_with("Checking ") {
                compiled += 1;
            }
            in_diag = false;
            continue;
        }
        if is_rustc_diag_start(trimmed) {
            in_diag = true;
            kept.push(line.to_string());
            continue;
        }
        if in_diag && is_rustc_diag_continuation(line, trimmed) {
            kept.push(line.to_string());
            continue;
        }
        in_diag = false;
        if trimmed.starts_with("Finished ")
            || trimmed.starts_with("error")
            || trimmed.contains("could not compile")
            || trimmed.contains("aborting due to")
            || trimmed.contains("generated ")
            || trimmed.starts_with("Caused by:")
            || trimmed.starts_with("note:")
        {
            kept.push(line.to_string());
        }
    }

    if kept.is_empty() && compiled > 0 {
        return format!("cargo: ok ({compiled} crates)");
    }
    if compiled > 0 && !kept.iter().any(|l| l.starts_with("Finished ")) {
        kept.insert(0, format!("cargo: {compiled} crates compiled/checked"));
    }
    kept.join("\n")
}

fn filter_cargo_test(raw: &str) -> String {
    let clean = strip_ansi(raw);
    let mut kept = Vec::new();
    let mut in_diag = false;
    let mut in_failures = false;
    let mut suites_ok = 0usize;
    let mut total_passed = 0usize;
    let mut total_failed = 0usize;
    let mut total_ignored = 0usize;

    static RESULT_RE: OnceLock<Option<Regex>> = OnceLock::new();
    let result_re = RESULT_RE
        .get_or_init(|| {
            Regex::new(r"^test result: (\w+)\. (\d+) passed; (\d+) failed; (\d+) ignored;").ok()
        })
        .as_ref();

    for line in clean.lines() {
        let trimmed = line.trim();

        if trimmed == "failures:" {
            in_failures = true;
            in_diag = false;
            kept.push(line.to_string());
            continue;
        }

        if let Some(re) = result_re
            && let Some(cap) = re.captures(trimmed)
        {
            in_failures = false;
            in_diag = false;
            let status = cap.get(1).map_or("", |m| m.as_str());
            let passed: usize = cap
                .get(2)
                .and_then(|m| m.as_str().parse().ok())
                .unwrap_or(0);
            let failed: usize = cap
                .get(3)
                .and_then(|m| m.as_str().parse().ok())
                .unwrap_or(0);
            let ignored: usize = cap
                .get(4)
                .and_then(|m| m.as_str().parse().ok())
                .unwrap_or(0);
            total_passed += passed;
            total_failed += failed;
            total_ignored += ignored;
            if status == "ok" && failed == 0 {
                suites_ok += 1;
            } else {
                kept.push(line.to_string());
            }
            continue;
        }

        if in_failures {
            kept.push(line.to_string());
            continue;
        }

        if trimmed.is_empty() {
            if in_diag {
                kept.push(String::new());
                in_diag = false;
            }
            continue;
        }

        if is_cargo_progress_line(trimmed)
            || trimmed.starts_with("Running ")
            || trimmed.starts_with("Doc-tests ")
            || trimmed.starts_with("running ")
            || (trimmed.starts_with("test ") && trimmed.ends_with(" ... ok"))
            || (trimmed.starts_with("test ") && trimmed.ends_with(" ... ignored"))
            || trimmed.starts_with("Finished ")
        {
            in_diag = false;
            continue;
        }

        if is_rustc_diag_start(trimmed) {
            in_diag = true;
            kept.push(line.to_string());
            continue;
        }

        if in_diag && is_rustc_diag_continuation(line, trimmed) {
            kept.push(line.to_string());
            continue;
        }
        in_diag = false;

        if (trimmed.starts_with("test ") && trimmed.contains("FAILED"))
            || trimmed.contains("panicked at")
            || trimmed.contains("assertion")
            || trimmed.starts_with("error")
            || trimmed.contains("could not compile")
            || trimmed.contains("test failed")
        {
            kept.push(line.to_string());
        }
    }

    if suites_ok > 0 || total_passed > 0 || total_failed > 0 {
        let summary = format!(
            "test summary: {} suites ok, {} passed, {} failed, {} ignored",
            suites_ok, total_passed, total_failed, total_ignored
        );
        kept.push(summary);
    }

    if kept.is_empty() {
        raw.to_string()
    } else {
        kept.join("\n")
    }
}

fn filter_test_runner(raw: &str) -> String {
    let clean = strip_ansi(raw);
    let mut kept = Vec::new();
    let mut passed_count = 0usize;
    let mut in_failure_block = false;

    for line in clean.lines() {
        let trimmed = line.trim();

        // Detect passing individual test lines across pytest, node --test, jest/vitest, go test.
        if !in_failure_block
            && (trimmed.starts_with("✔ ")
                || trimmed.starts_with("✓ ")
                || trimmed.starts_with("PASS ")
                || trimmed.starts_with("--- PASS:")
                || trimmed.starts_with("=== RUN ")
                || trimmed.starts_with("ok  \t")
                || trimmed.ends_with(" PASSED")
                || trimmed.contains(" PASSED [")
                || (trimmed.chars().all(|c| c == '.' || c == 's' || c == ' ')
                    && trimmed.contains('.')))
        {
            passed_count += 1;
            continue;
        }

        // Skip pytest/node boilerplate lines outside failure blocks.
        if !in_failure_block
            && (trimmed.starts_with("platform ")
                || trimmed.starts_with("cachedir:")
                || trimmed.starts_with("rootdir:")
                || trimmed.starts_with("configfile:")
                || trimmed.starts_with("plugins:")
                || trimmed.starts_with("collecting ...")
                || trimmed.starts_with("collected ")
                || trimmed.starts_with("ℹ suites 0")
                || trimmed.starts_with("ℹ cancelled 0")
                || trimmed.starts_with("ℹ skipped 0")
                || trimmed.starts_with("ℹ todo 0")
                || trimmed.starts_with("ℹ duration_ms "))
        {
            continue;
        }

        if trimmed.starts_with("===") && trimmed.contains("FAILURES")
            || trimmed.starts_with("___ ")
            || trimmed.starts_with("FAIL ")
            || trimmed.starts_with("FAILED ")
            || trimmed.starts_with("--- FAIL:")
            || trimmed.starts_with("✖ ")
            || trimmed.starts_with("Traceback (most recent call last):")
        {
            in_failure_block = true;
            kept.push(line.to_string());
            continue;
        }

        if in_failure_block {
            if trimmed.starts_with("===")
                && (trimmed.contains("short test summary") || trimmed.contains(" passed"))
            {
                in_failure_block = false;
            }
            kept.push(line.to_string());
            continue;
        }

        if trimmed.starts_with("E   ")
            || trimmed.contains("FAILED")
            || trimmed.contains("ERROR")
            || trimmed.contains("AssertionError")
            || trimmed.contains("Assert")
            || trimmed.starts_with("ℹ tests ")
            || trimmed.starts_with("ℹ pass ")
            || trimmed.starts_with("ℹ fail ")
            || (trimmed.starts_with("===") && trimmed.ends_with("==="))
            || trimmed.starts_with("Tests:")
            || trimmed.starts_with("Test Suites:")
            || trimmed.starts_with("FAIL\t")
        {
            kept.push(line.to_string());
        }
    }

    if kept.is_empty() && passed_count > 0 {
        return format!("tests: ok ({passed_count} passed, 0 failed)");
    }
    if passed_count > 0
        && !kept
            .iter()
            .any(|l| l.contains("passed") || l.contains("pass "))
    {
        kept.push(format!("({passed_count} passed lines omitted)"));
    }
    if kept.is_empty() {
        raw.to_string()
    } else {
        kept.join("\n")
    }
}

fn filter_git(subcommand: Option<&str>, raw: &str) -> String {
    let collapsed = collapse_line_ending_warnings(raw);
    let raw = collapsed.as_str();
    match subcommand {
        Some("push" | "pull" | "fetch" | "clone") => filter_git_transfer(raw),
        Some("status") => filter_git_status(raw),
        Some("log") => filter_git_log(raw),
        Some("diff" | "show") => filter_git_diff(raw),
        _ => filter_generic(raw),
    }
}

/// Git prints one `warning: in the working copy of 'x', LF will be replaced by CRLF …` line per file on Windows; two or
/// more become one line naming the first files.
fn collapse_line_ending_warnings(raw: &str) -> String {
    let file_of = |line: &str| {
        let rest = line.strip_prefix("warning: in the working copy of '")?;
        let (file, tail) = rest.split_once("', ")?;
        (tail.contains("will be replaced by") && tail.ends_with("the next time Git touches it"))
            .then_some(file.to_string())
    };
    let files: Vec<String> = raw.lines().filter_map(file_of).collect();
    if files.len() < 2 {
        return raw.to_string();
    }
    let mut out = String::with_capacity(raw.len());
    let mut said = false;
    for line in raw.lines() {
        if file_of(line).is_some() {
            if !said {
                let shown: Vec<&str> = files.iter().take(5).map(String::as_str).collect();
                let more = files.len().saturating_sub(5);
                out.push_str(&format!(
                    "warning: Git will change line endings in {} files the next time it touches them: {}{}",
                    files.len(),
                    shown.join(", "),
                    if more > 0 { format!(" and {more} more") } else { String::new() }
                ));
                out.push('\n');
                said = true;
            }
            continue;
        }
        out.push_str(line);
        out.push('\n');
    }
    out
}

/// `git push/pull/fetch/clone` keep their ref updates, summaries and errors; object-counting progress, `remote:`
/// banners (such as the link to open a pull request) and `hint:` advice go.
fn filter_git_transfer(raw: &str) -> String {
    const PROGRESS: &[&str] = &[
        "Enumerating objects",
        "Counting objects",
        "Compressing objects",
        "Writing objects",
        "Receiving objects",
        "Resolving deltas",
        "Unpacking objects",
        "Delta compression",
        "Total ",
    ];
    let mut out = String::with_capacity(raw.len());
    for line in raw.lines() {
        let line = line.rsplit('\r').next().unwrap_or(line);
        let low = line.to_ascii_lowercase();
        let alarming = ["error", "fatal", "rejected", "denied", "failed", "warning"]
            .iter()
            .any(|w| low.contains(w));
        if let Some(rest) = line.strip_prefix("remote: ")
            && (!alarming || PROGRESS.iter().any(|p| rest.starts_with(p)))
        {
            continue;
        }
        if line == "remote:" || line.starts_with("hint: ") || line == "hint:" {
            continue;
        }
        if PROGRESS.iter().any(|p| line.starts_with(p)) {
            continue;
        }
        out.push_str(line);
        out.push('\n');
    }
    out
}

fn filter_git_status(raw: &str) -> String {
    let mut out = Vec::new();
    let mut section = "";
    for line in raw.lines() {
        let trimmed = line.trim();
        if trimmed.is_empty() || trimmed.starts_with("(use \"git ") {
            continue;
        }
        if trimmed.starts_with("On branch ")
            || trimmed.starts_with("HEAD detached")
            || trimmed.starts_with("Your branch ")
            || trimmed.starts_with("nothing to commit")
            || trimmed.starts_with("You have unmerged paths")
        {
            out.push(trimmed.to_string());
            continue;
        }
        if trimmed == "Changes to be committed:" {
            section = "staged";
            continue;
        }
        if trimmed == "Changes not staged for commit:" {
            section = "unstaged";
            continue;
        }
        if trimmed == "Untracked files:" {
            section = "untracked";
            continue;
        }
        if trimmed == "Unmerged paths:" {
            section = "conflict";
            continue;
        }
        if let Some(rest) = trimmed.strip_prefix("modified:") {
            let code = if section == "staged" { "M " } else { " M" };
            out.push(format!("{code} {}", rest.trim()));
        } else if let Some(rest) = trimmed.strip_prefix("new file:") {
            out.push(format!("A  {}", rest.trim()));
        } else if let Some(rest) = trimmed.strip_prefix("deleted:") {
            let code = if section == "staged" { "D " } else { " D" };
            out.push(format!("{code} {}", rest.trim()));
        } else if let Some(rest) = trimmed.strip_prefix("renamed:") {
            out.push(format!("R  {}", rest.trim()));
        } else if let Some(rest) = trimmed.strip_prefix("both modified:") {
            out.push(format!("UU {}", rest.trim()));
        } else if trimmed.starts_with("no changes added")
            || trimmed.starts_with("nothing added to commit")
        {
            // git's closing hint: dropped, and never read as an untracked file.
        } else if section == "untracked" && line.starts_with(char::is_whitespace) {
            out.push(format!("?? {trimmed}"));
        } else {
            out.push(trimmed.to_string());
        }
    }
    if out.is_empty() {
        raw.to_string()
    } else {
        out.join("\n")
    }
}

fn filter_git_log(raw: &str) -> String {
    let lines: Vec<&str> = raw.lines().collect();
    if !lines.iter().any(|l| l.starts_with("commit ")) {
        return filter_generic(raw);
    }
    let mut out = Vec::new();
    let mut sha = String::new();
    let mut author = String::new();
    let mut date = String::new();
    let mut subject = String::new();
    let flush = |out: &mut Vec<String>,
                 sha: &mut String,
                 author: &mut String,
                 date: &mut String,
                 subject: &mut String| {
        if !sha.is_empty() {
            let short = &sha[..sha.len().min(8)];
            let a = author.split('<').next().unwrap_or(author).trim();
            out.push(format!("{short} {date} [{a}] {subject}"));
            sha.clear();
            author.clear();
            date.clear();
            subject.clear();
        }
    };
    for line in lines {
        if let Some(rest) = line.strip_prefix("commit ") {
            flush(&mut out, &mut sha, &mut author, &mut date, &mut subject);
            sha = rest.split_whitespace().next().unwrap_or("").to_string();
        } else if let Some(rest) = line.strip_prefix("Author:") {
            author = rest.trim().to_string();
        } else if let Some(rest) = line.strip_prefix("Date:") {
            // Keep compact date (drop timezone noise when standard git date).
            let tokens: Vec<&str> = rest.split_whitespace().collect();
            date = if tokens.len() >= 5 {
                format!("{} {} {}", tokens[1], tokens[2], tokens[4])
            } else {
                rest.trim().to_string()
            };
        } else if line.starts_with("Merge:") {
            continue;
        } else if subject.is_empty() && !line.trim().is_empty() {
            subject = line.trim().to_string();
        } else if line.contains("files changed") || line.contains("file changed") {
            flush(&mut out, &mut sha, &mut author, &mut date, &mut subject);
            out.push(format!("  {}", line.trim()));
        }
    }
    flush(&mut out, &mut sha, &mut author, &mut date, &mut subject);
    if out.is_empty() {
        raw.to_string()
    } else {
        out.join("\n")
    }
}

fn filter_git_diff(raw: &str) -> String {
    let lines: Vec<&str> = raw.lines().collect();
    let mut out = Vec::new();
    let mut i = 0;
    while i < lines.len() {
        let line = lines[i];
        if line.starts_with("index ")
            || line.starts_with("old mode ")
            || line.starts_with("new mode ")
        {
            i += 1;
            continue;
        }
        // Keep headers, hunk markers, additions/deletions, conflict markers verbatim.
        let is_header = line.starts_with("diff --git ")
            || line.starts_with("--- ")
            || line.starts_with("+++ ")
            || line.starts_with("@@ ")
            || line.starts_with("Binary files ")
            || line.starts_with("new file mode ")
            || line.starts_with("deleted file mode ")
            || line.starts_with("rename from ")
            || line.starts_with("rename to ");
        let is_change = (line.starts_with('+') && !line.starts_with("+++ "))
            || (line.starts_with('-') && !line.starts_with("--- "))
            || line.starts_with("<<<<<<<")
            || line.starts_with("=======")
            || line.starts_with(">>>>>>>");

        if is_header || is_change {
            out.push(line);
        } else if line.starts_with(' ') {
            // Preserve 1 line of adjacent unchanged context around any edit as byte-exact anchor.
            let prev_change = i > 0 && is_diff_edit_line(lines[i - 1]);
            let next_change = i + 1 < lines.len() && is_diff_edit_line(lines[i + 1]);
            if prev_change || next_change {
                out.push(line);
            }
        } else if !line.is_empty() {
            out.push(line);
        }
        i += 1;
    }
    if out.is_empty() {
        raw.to_string()
    } else {
        out.join("\n")
    }
}

fn is_diff_edit_line(line: &str) -> bool {
    (line.starts_with('+') && !line.starts_with("+++ "))
        || (line.starts_with('-') && !line.starts_with("--- "))
}

fn filter_search(raw: &str) -> String {
    let clean = strip_ansi(raw);
    let mut groups: BTreeMap<String, Vec<String>> = BTreeMap::new();
    let mut order: Vec<String> = Vec::new();
    let mut ungrouped: Vec<String> = Vec::new();

    for line in clean.lines() {
        if let Some((path, rest)) = split_path_line(line) {
            if !groups.contains_key(path) {
                order.push(path.to_string());
            }
            groups
                .entry(path.to_string())
                .or_default()
                .push(rest.to_string());
        } else if !line.trim().is_empty() {
            ungrouped.push(line.to_string());
        }
    }

    if groups.is_empty() {
        return filter_generic(raw);
    }

    let mut out = Vec::new();
    for path in &order {
        if let Some(hits) = groups.get(path) {
            out.push(format!("{path}:"));
            for hit in hits {
                out.push(format!("  {hit}"));
            }
        }
    }
    for u in ungrouped {
        out.push(u);
    }
    out.join("\n")
}

/// Split `path:line:rest` or `C:\path:line:rest` into `(&str path, &str "line:rest")`.
fn split_path_line(line: &str) -> Option<(&str, &str)> {
    let start = if line.len() > 2 && line.as_bytes()[1] == b':' {
        2
    } else {
        0
    };
    let rel_colon = line[start..].find(':')?;
    let colon = start + rel_colon;
    let path = &line[..colon];
    if path.is_empty() || path.chars().any(char::is_whitespace) {
        return None;
    }
    let after = &line[colon + 1..];
    let digits = after.bytes().take_while(u8::is_ascii_digit).count();
    if digits == 0 || after.as_bytes().get(digits) != Some(&b':') {
        return None;
    }
    Some((path, after))
}

fn filter_linter(raw: &str) -> String {
    static TSC_RE: OnceLock<Option<Regex>> = OnceLock::new();
    let tsc_re = TSC_RE
        .get_or_init(|| Regex::new(r"^([^\s(]+)\((\d+),(\d+)\):\s*(.+)$").ok())
        .as_ref();

    let clean = strip_ansi(raw);
    let mut groups: BTreeMap<String, Vec<String>> = BTreeMap::new();
    let mut order: Vec<String> = Vec::new();
    let mut summaries: Vec<String> = Vec::new();

    for line in clean.lines() {
        let trimmed = line.trim();
        if trimmed.is_empty()
            || trimmed.starts_with("help:")
            || trimmed.starts_with("[*]")
            || trimmed.starts_with("= help:")
        {
            continue;
        }
        if let Some(re) = tsc_re
            && let Some(cap) = re.captures(trimmed)
        {
            let path = cap.get(1).map_or("", |m| m.as_str());
            let ln = cap.get(2).map_or("", |m| m.as_str());
            let col = cap.get(3).map_or("", |m| m.as_str());
            let msg = cap.get(4).map_or("", |m| m.as_str());
            if !groups.contains_key(path) {
                order.push(path.to_string());
            }
            groups
                .entry(path.to_string())
                .or_default()
                .push(format!("{ln}:{col} {msg}"));
            continue;
        }
        if let Some((path, rest)) = split_path_line(trimmed) {
            if !groups.contains_key(path) {
                order.push(path.to_string());
            }
            groups
                .entry(path.to_string())
                .or_default()
                .push(rest.to_string());
            continue;
        }
        if trimmed.contains("Found ")
            || trimmed.contains("error")
            || trimmed.contains("warning")
            || trimmed.contains("problem")
        {
            summaries.push(trimmed.to_string());
        }
    }

    if groups.is_empty() {
        return filter_generic(raw);
    }

    let mut out = Vec::new();
    for path in &order {
        if let Some(diags) = groups.get(path) {
            out.push(format!("{path}:"));
            for d in diags {
                out.push(format!("  {d}"));
            }
        }
    }
    for s in summaries {
        out.push(s);
    }
    out.join("\n")
}

fn filter_generic(raw: &str) -> String {
    if raw.len() <= GENERIC_THRESHOLD_BYTES {
        return raw.to_string();
    }
    let lines: Vec<&str> = raw.lines().collect();
    if lines.len() <= 60 {
        return raw.to_string();
    }
    let head = 20usize;
    let tail = 20usize;
    let mut out: Vec<String> = Vec::new();
    for l in &lines[..head] {
        out.push((*l).to_string());
    }
    let mut middle_markers = Vec::new();
    for (idx, l) in lines[head..lines.len() - tail].iter().enumerate() {
        if is_important_line(l) && middle_markers.len() < 120 {
            middle_markers.push(format!("L{}: {l}", head + idx + 1));
        }
    }
    let omitted = lines
        .len()
        .saturating_sub(head + tail + middle_markers.len());
    out.push(format!(
        "[... {omitted} lines omitted, {} marker lines kept ...]",
        middle_markers.len()
    ));
    out.extend(middle_markers);
    out.push("[... tail ...]".to_string());
    for l in &lines[lines.len() - tail..] {
        out.push((*l).to_string());
    }
    out.join("\n")
}

fn is_important_line(line: &str) -> bool {
    let low = line.to_ascii_lowercase();
    low.contains("error")
        || low.contains("failed")
        || low.contains("panic")
        || low.contains("exception")
        || low.contains("traceback")
        || low.contains("assertion")
        || low.contains("warning:")
        || line.contains("--> ")
        || line.starts_with("<<<<<<<")
}

#[cfg(feature = "code")]
fn has_error_markers(text: &str) -> bool {
    text.lines().any(is_important_line)
}

/// Link failing tests or compiler errors to their symbols in the project's Footnote Code graph (read-only).
#[cfg(feature = "code")]
fn resolve_code_links(cwd: &Path, digest: &str) -> String {
    let Ok(db) = crate::app::code_db(cwd) else {
        return String::new();
    };
    if !db.is_file() {
        return String::new();
    }
    let Ok(conn) =
        rusqlite::Connection::open_with_flags(&db, rusqlite::OpenFlags::SQLITE_OPEN_READ_ONLY)
    else {
        return String::new();
    };

    static FILE_LINE_RE: OnceLock<Option<Regex>> = OnceLock::new();
    let re = FILE_LINE_RE
        .get_or_init(|| {
            Regex::new(r"([A-Za-z0-9_./\\-]+\.(?:rs|py|ts|tsx|js|jsx|go|java)):(\d+)").ok()
        })
        .as_ref();
    let Some(re) = re else {
        return String::new();
    };

    let mut links = Vec::new();
    let mut seen_syms: std::collections::HashSet<String> = std::collections::HashSet::new();

    for cap in re.captures_iter(digest) {
        if links.len() >= 3 {
            break;
        }
        let raw_path = cap.get(1).map_or("", |m| m.as_str()).replace('\\', "/");
        let path = raw_path.trim_start_matches("./");
        let Ok(line) = cap.get(2).map_or("", |m| m.as_str()).parse::<i64>() else {
            continue;
        };
        let row: Option<(String, String, String, i64, i64)> = conn
            .query_row(
                "SELECT s.name, s.kind, f.path, s.line,
                        (SELECT count(DISTINCT r.caller_id) FROM refs r WHERE r.symbol_id = s.id AND r.caller_id != s.id)
                 FROM symbols s
                 JOIN files f ON f.id = s.file_id
                 WHERE replace(f.path, '\\', '/') = ?1
                   AND s.kind != 'module'
                   AND s.line <= ?2
                   AND (s.end_line IS NULL OR s.end_line >= ?2)
                 ORDER BY s.line DESC LIMIT 1",
                rusqlite::params![path, line],
                |r| Ok((r.get(0)?, r.get(1)?, r.get(2)?, r.get(3)?, r.get(4)?)),
            )
            .ok();
        if let Some((name, kind, fpath, sline, callers)) = row {
            let key = format!("{name}@{fpath}:{sline}");
            if seen_syms.insert(key) {
                links.push(format!(
                    "  {} ({}, {}:{}, {} callers) -> `footnote code {}`",
                    name,
                    kind,
                    fpath.replace('\\', "/"),
                    sline,
                    callers,
                    name
                ));
            }
        }
    }

    if links.is_empty() {
        String::new()
    } else {
        format!("code graph:\n{}", links.join("\n"))
    }
}

fn outputs_dir() -> Result<PathBuf> {
    let dir = crate::state::state_dir()?.join("outputs");
    crate::state::ensure_private_dir(&dir)?;
    Ok(dir)
}

pub(crate) fn store_raw_output(raw: &str) -> Result<String> {
    let dir = outputs_dir()?;
    prune_handles(&dir);
    let now = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap_or_default()
        .as_nanos();
    let seed = format!("{now}:{}:{}", std::process::id(), raw.len());
    let mut hash_input = seed.into_bytes();
    hash_input.extend_from_slice(&raw.as_bytes()[..raw.len().min(4096)]);
    let digest = footnote_core::hash(&hash_input);
    let id = format!("h-{}", &digest[..12]);
    let target = dir.join(format!("{id}.txt"));
    let tmp = dir.join(format!(".{id}.{}.tmp", std::process::id()));
    fs::write(&tmp, raw.as_bytes()).with_context(|| format!("write {}", tmp.display()))?;
    fs::rename(&tmp, &target).with_context(|| format!("persist {}", target.display()))?;
    Ok(id)
}

fn remove_handle(id: &str) {
    if let Ok(dir) = outputs_dir() {
        let _ = fs::remove_file(dir.join(format!("{id}.txt")));
    }
}

fn prune_handles(dir: &Path) {
    let Ok(rd) = fs::read_dir(dir) else {
        return;
    };
    let cutoff = SystemTime::now()
        .checked_sub(Duration::from_secs(HANDLE_TTL_SECS))
        .unwrap_or(UNIX_EPOCH);
    let mut entries: Vec<(SystemTime, PathBuf)> = Vec::new();
    for entry in rd.flatten() {
        let path = entry.path();
        if path.extension().and_then(|e| e.to_str()) != Some("txt") {
            continue;
        }
        let mtime = entry
            .metadata()
            .and_then(|m| m.modified())
            .unwrap_or(UNIX_EPOCH);
        if mtime < cutoff {
            let _ = fs::remove_file(&path);
        } else {
            entries.push((mtime, path));
        }
    }
    if entries.len() > MAX_HANDLES {
        entries.sort_by_key(|(t, _)| *t);
        for (_, path) in &entries[..entries.len() - MAX_HANDLES] {
            let _ = fs::remove_file(path);
        }
    }
}

fn validate_handle_id(id: &str) -> Result<()> {
    let valid = (3..=32).contains(&id.len())
        && id.starts_with("h-")
        && id.chars().all(|c| c.is_ascii_alphanumeric() || c == '-');
    if !valid {
        bail!("invalid output handle id `{id}` (expected `h-<hex>`)");
    }
    Ok(())
}

#[derive(Debug, Clone)]
pub struct OutputQuery {
    pub id: String,
    pub grep: Option<String>,
    pub head: Option<usize>,
    pub tail: Option<usize>,
    pub lines: Option<String>,
}

/// Read or search a stored full output handle (`footnote output <id>`).
pub fn output_cli(q: &OutputQuery) -> Result<Value> {
    validate_handle_id(&q.id)?;
    let path = outputs_dir()?.join(format!("{}.txt", q.id));
    if !path.is_file() {
        bail!(
            "output handle `{}` not found (expired, pruned, or not stored)",
            q.id
        );
    }
    let text = fs::read_to_string(&path).with_context(|| format!("read {}", path.display()))?;
    let all_lines: Vec<&str> = text.lines().collect();
    let total_lines = all_lines.len();

    let mut selected: Vec<(usize, &str)> = all_lines
        .iter()
        .enumerate()
        .map(|(i, l)| (i + 1, *l))
        .collect();

    if let Some(range) = &q.lines {
        let (a, b) = parse_line_range(range)?;
        selected.retain(|(ln, _)| *ln >= a && *ln <= b);
    }

    if let Some(pat) = &q.grep {
        if let Ok(re) = Regex::new(pat) {
            selected.retain(|(_, l)| re.is_match(l));
        } else {
            let needle = pat.to_ascii_lowercase();
            selected.retain(|(_, l)| l.to_ascii_lowercase().contains(&needle));
        }
    }

    if let Some(n) = q.head {
        selected.truncate(n);
    } else if let Some(n) = q.tail
        && selected.len() > n
    {
        selected = selected.split_off(selected.len() - n);
    }

    let rendered = selected
        .iter()
        .map(|(ln, l)| format!("{ln}: {l}"))
        .collect::<Vec<_>>()
        .join("\n");

    log_lean_retrieve(&q.id, rendered.len());

    Ok(json!({
        "id": q.id,
        "total_lines": total_lines,
        "returned_lines": selected.len(),
        "content": rendered,
    }))
}

fn parse_line_range(spec: &str) -> Result<(usize, usize)> {
    let (a, b) = spec
        .split_once(':')
        .or_else(|| spec.split_once('-'))
        .with_context(|| format!("invalid --lines range `{spec}` (expected start:end)"))?;
    let start: usize = a.trim().parse().context("invalid start line")?;
    let end: usize = b.trim().parse().context("invalid end line")?;
    if start == 0 || end < start {
        bail!("invalid --lines range `{spec}` (1-based start <= end required)");
    }
    Ok((start, end))
}

fn log_lean_run(
    family: CommandFamily,
    before: usize,
    after: usize,
    handle: Option<&str>,
    exit_code: i32,
) {
    let Ok(state) = crate::state::state_dir() else {
        return;
    };
    let on = footnote_core::config::product_settings(&state, "usage")
        .map_or(true, |v| v["lean_log"].as_bool().unwrap_or(true));
    if !on {
        return;
    }
    let dir = state.join("usage");
    let path = dir.join("lean.jsonl");
    if fs::metadata(&path).is_ok_and(|m| m.len() > 512 * 1024) {
        let _ = fs::rename(&path, path.with_extension("jsonl.old"));
    }
    let row = json!({
        "t": footnote_core::audit::now_ms(),
        "tool": "run",
        "family": family.as_str(),
        "before": before,
        "after": after,
        "stored": handle.is_some(),
        "handle": handle,
        "exit_code": exit_code,
    });
    let _ =
        fs::create_dir_all(&dir).and_then(|()| crate::state::append_line(&path, &row.to_string()));
}

fn log_lean_retrieve(handle: &str, returned_bytes: usize) {
    let Ok(state) = crate::state::state_dir() else {
        return;
    };
    let on = footnote_core::config::product_settings(&state, "usage")
        .map_or(true, |v| v["lean_log"].as_bool().unwrap_or(true));
    if !on {
        return;
    }
    let dir = state.join("usage");
    let path = dir.join("lean.jsonl");
    let row = json!({
        "t": footnote_core::audit::now_ms(),
        "tool": "output",
        "handle": handle,
        "miss": true,
        "before": 0,
        "after": returned_bytes,
    });
    let _ =
        fs::create_dir_all(&dir).and_then(|()| crate::state::append_line(&path, &row.to_string()));
}

/// Handle a PreToolUse hook event from Claude Code, Codex or Antigravity:
/// rewrite eligible shell commands to `footnote run -- <cmd>` using each CLI's native wire format.
/// Returns `None` when the event is not a rewritable shell call (passthrough untouched).
#[cfg(any(feature = "memory", test))]
#[must_use]
pub fn pre_tool_use_hook(event: &Value) -> Option<Value> {
    let (agent, tool) = hook_agent_tool(event);
    match hook_decision(event, agent, tool).0 {
        HookDecision::Rewrite(output) => Some(output),
        _ => None,
    }
}

enum HookDecision {
    Rewrite(Value),
    Pass(&'static str),
    Error(&'static str),
}

fn hook_agent_tool(event: &Value) -> (&'static str, &str) {
    let agent = if event.get("toolCall").is_some()
        || event.get("conversationId").is_some()
        || event.get("hookEventName").is_some()
    {
        "antigravity"
    } else if event.get("turn_id").is_some() {
        "codex"
    } else {
        "claude-code"
    };
    let tool = event["tool_name"]
        .as_str()
        .or_else(|| event["toolName"].as_str())
        .or_else(|| event["toolCall"]["name"].as_str())
        .unwrap_or("");
    (agent, tool)
}

fn hook_decision(event: &Value, agent: &str, tool: &str) -> (HookDecision, Option<&'static str>) {
    use HookDecision::{Error, Pass, Rewrite};
    let ev_name = event["hook_event_name"]
        .as_str()
        .or_else(|| event["hookEventName"].as_str())
        .unwrap_or("");
    if !ev_name.is_empty() && ev_name != "PreToolUse" {
        return (Pass("wrong-event"), None);
    }
    #[cfg(feature = "code")]
    if tool == "Read" && agent != "antigravity" {
        return (
            outline_instead(event).map_or(Pass("not-covered"), |reason| {
                Rewrite(json!({"hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "deny",
                    "permissionDecisionReason": reason,
                }}))
            }),
            None,
        );
    }
    if !SHELL_TOOLS
        .iter()
        .any(|name| tool.eq_ignore_ascii_case(name))
    {
        return (Pass("not-covered"), None);
    }
    let Some(input) = event
        .get("tool_input")
        .or_else(|| event.get("toolInput"))
        .or_else(|| event.get("toolCall").and_then(|tc| tc.get("args")))
        .and_then(Value::as_object)
    else {
        return (Error("missing-input"), None);
    };
    let (cmd_key, cmd_str) = if let Some(s) = input.get("command").and_then(Value::as_str) {
        ("command", s)
    } else if let Some(s) = input.get("CommandLine").and_then(Value::as_str) {
        ("CommandLine", s)
    } else {
        return (Error("missing-command"), None);
    };
    // Codex (#573) sends `turn_id`. It names its tool `Bash` but runs PowerShell on Windows, and its shell's PATH can
    // lack `footnote` even when this hook's has it, so it always gets the full path.
    let shell = shell_for_agent(agent, tool);
    let points = match rewrite_points(cmd_str, shell) {
        Ok(points) => points,
        Err(reason) => return (Pass(reason), logged_program(cmd_str)),
    };
    let bin_cmd = match std::env::current_exe() {
        Ok(exe) if agent == "codex" || !footnote_on_path() => format_exe_for_shell(&exe, shell),
        _ => "footnote".to_string(),
    };
    let program = logged_program(&cmd_str[points[0].0..]);
    let rewritten = render_rewrite(cmd_str, &bin_cmd, points);
    if agent == "antigravity" {
        // Antigravity PreToolUse contract: shallow merge into `toolCall.args` via `overwrite`.
        let mut overwrite = serde_json::Map::new();
        overwrite.insert(cmd_key.to_string(), json!(rewritten));
        return (
            Rewrite(json!({
                "decision": "allow",
                "overwrite": overwrite,
            })),
            program,
        );
    }
    let mut updated = input.clone();
    updated.insert(cmd_key.to_string(), json!(rewritten));
    (
        Rewrite(json!({
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "allow",
                "updatedInput": updated,
            }
        })),
        program,
    )
}

const SHELL_TOOLS: &[&str] = &[
    "bash",
    "powershell",
    "shell",
    "run_command",
    "run_shell_command",
    "command",
    "terminal",
];

fn logged_program(command: &str) -> Option<&'static str> {
    const PROGRAMS: &[&str] = &[
        "git",
        "cargo",
        "rg",
        "grep",
        "ls",
        "find",
        "cat",
        "sort",
        "curl",
        "python",
        "python3",
        "py",
        "npm",
        "pnpm",
        "yarn",
        "bun",
        "docker",
        "kubectl",
        "gh",
        "uv",
        "pip",
        "go",
        "pytest",
        "ruff",
        "tsc",
        "eslint",
        "jest",
        "vitest",
        "footnote",
        "rtk",
        "get-childitem",
    ];
    let token = command
        .split_ascii_whitespace()
        .next()?
        .trim_matches(['"', '\'']);
    let name = token.rsplit(['/', '\\']).next()?;
    let stem = Path::new(name).file_stem()?.to_str()?;
    PROGRAMS
        .iter()
        .copied()
        .find(|name| stem.eq_ignore_ascii_case(name))
}

/// Lines past which a whole-file Read is answered with the file's outline (#240).
#[cfg(feature = "code")]
const OUTLINE_LINES: usize = 500;
/// Most outline entries listed; past it the agent still has offset and limit.
#[cfg(feature = "code")]
const OUTLINE_MAX: usize = 150;

/// Graph-first reads (#240): a whole-file Claude Code `Read` of a large file the code graph indexed gets the file's outline
/// instead, so the agent reads only the part it needs. Anything else (a slice, a small or unindexed file) passes through.
#[cfg(feature = "code")]
fn outline_instead(event: &Value) -> Option<String> {
    let input = event["tool_input"].as_object()?;
    if input.contains_key("offset") || input.contains_key("limit") {
        return None;
    }
    let file = Path::new(input.get("file_path")?.as_str()?);
    let lines = fs::read(file).ok()?.iter().filter(|&&b| b == b'\n').count();
    if lines < OUTLINE_LINES {
        return None;
    }
    // shortcut: the graph is found from the session's cwd only, so a session started in a subfolder of the indexed root
    // gets no outline; walk up to the indexed root if that shows up in the paired benchmark.
    let root = Path::new(event["cwd"].as_str()?);
    let rel = file
        .canonicalize()
        .ok()?
        .strip_prefix(root.canonicalize().ok()?)
        .ok()?
        .to_string_lossy()
        .replace('\\', "/");
    let db = crate::app::code_db(root).ok().filter(|d| d.exists())?;
    let v = footnote_code::outline(&db, &rel).ok()?;
    let symbols = v["symbols"].as_array().filter(|s| !s.is_empty())?;
    let mut list: Vec<String> = symbols
        .iter()
        .take(OUTLINE_MAX)
        .map(|s| {
            format!(
                "{}-{} {} {}",
                s["lines"][0],
                s["lines"][1],
                s["kind"].as_str().unwrap_or_default(),
                s["name"].as_str().unwrap_or_default()
            )
        })
        .collect();
    if symbols.len() > OUTLINE_MAX {
        list.push(format!("... {} more", symbols.len() - OUTLINE_MAX));
    }
    Some(format!(
        "{rel} has {lines} lines, so Footnote gives its outline first (lines, kind, name):\n{}\n\
         Read it again with offset and limit for the part you need (limit 2000 reads it whole).",
        list.join("\n")
    ))
}

/// Standalone `footnote hook lean` entrypoint: fast, SQLite-free PreToolUse command rewriter.
/// Never fails closed against the user's shell; any parse or I/O error passes through silently.
pub fn run_lean_hook() {
    const MAX_HOOK_EVENT: u64 = 2 * 1024 * 1024;
    let state = crate::state::state_dir().ok();
    let settings = state
        .as_deref()
        .and_then(|state| footnote_core::config::product_settings(state, "usage").ok());
    let allowed = |key: &str| {
        settings
            .as_ref()
            .and_then(|v| v[key].as_bool())
            .unwrap_or(true)
    };
    let log = |agent, tool, program, decision: &HookDecision| {
        if allowed("lean_log")
            && let Some(state) = &state
        {
            log_hook_decision(state, agent, tool, program, decision);
        }
    };

    let mut raw = String::new();
    if std::io::stdin()
        .take(MAX_HOOK_EVENT + 1)
        .read_to_string(&mut raw)
        .is_err()
    {
        log("unknown", "", None, &HookDecision::Error("read-error"));
        return;
    }
    if raw.len() as u64 > MAX_HOOK_EVENT {
        log("unknown", "", None, &HookDecision::Error("too-large"));
        return;
    }
    let event = match serde_json::from_str::<Value>(&raw) {
        Ok(event) if event.is_object() => event,
        _ => {
            log("unknown", "", None, &HookDecision::Error("invalid-event"));
            return;
        }
    };
    let (agent, tool) = hook_agent_tool(&event);
    let (decision, program) = if allowed("lean_enabled") {
        hook_decision(&event, agent, tool)
    } else {
        (HookDecision::Pass("disabled"), None)
    };
    log(agent, tool, program, &decision);

    if let HookDecision::Rewrite(out) = decision {
        println!("{out}");
    } else if agent == "antigravity" {
        // Antigravity PreToolUse requires an explicit `decision`; `{}` denies the tool call.
        println!("{{\"decision\":\"allow\"}}");
    }
}

pub(crate) const LEAN_HOOK_LOG: &str = "lean-hooks.jsonl";

fn log_hook_decision(
    state: &Path,
    agent: &str,
    tool: &str,
    program: Option<&str>,
    decision: &HookDecision,
) {
    let dir = state.join("usage");
    let path = dir.join(LEAN_HOOK_LOG);
    let open = || fs::OpenOptions::new().create(true).append(true).open(&path);
    let mut file = match open() {
        Ok(file) => file,
        Err(e) if e.kind() == std::io::ErrorKind::NotFound => {
            let Ok(file) = crate::state::ensure_private_dir(&dir).and_then(|()| Ok(open()?)) else {
                return;
            };
            file
        }
        Err(_) => return,
    };
    if file.metadata().is_ok_and(|m| m.len() >= 512 * 1024) {
        drop(file);
        let _ = fs::rename(&path, path.with_extension("jsonl.old"));
        let Ok(next) = open() else { return };
        file = next;
    }
    // Tool names can come from plugins. Persist only the fixed vocabulary.
    let tool = SHELL_TOOLS
        .iter()
        .copied()
        .chain(["read"])
        .find(|known| tool.eq_ignore_ascii_case(known))
        .unwrap_or("other");
    let (decision, reason) = match decision {
        HookDecision::Rewrite(_) => ("rewrite", None),
        HookDecision::Pass(reason) => ("pass", Some(*reason)),
        HookDecision::Error(reason) => ("error", Some(*reason)),
    };
    let row = json!({
        "t": footnote_core::audit::now_ms(),
        "agent": agent, "tool": tool, "program": program,
        "decision": decision, "reason": reason,
    });
    let mut line = row.to_string();
    line.push('\n');
    let _ = file.write_all(line.as_bytes());
}

#[cfg(test)]
mod tests {
    use super::*;

    /// #573: Codex's shell may not have `footnote` on PATH, so its rewrite calls this binary by its full path.
    #[test]
    fn codex_rewrites_call_the_binary_by_its_full_path() {
        let event = |extra: Value| {
            let mut e = json!({"hook_event_name": "PreToolUse", "tool_name": "Bash",
                "tool_input": {"command": "git log -3"}, "session_id": "s"});
            e.as_object_mut()
                .unwrap()
                .extend(extra.as_object().unwrap().clone());
            e
        };
        let codex = pre_tool_use_hook(&event(json!({"turn_id": "t"}))).unwrap();
        let cmd = codex["hookSpecificOutput"]["updatedInput"]["command"]
            .as_str()
            .unwrap();
        let exe = format_exe_for_shell(&std::env::current_exe().unwrap(), Shell::PowerShell);
        assert_eq!(cmd, format!("{exe} run -- git log -3"));
        let claude = pre_tool_use_hook(&event(json!({}))).unwrap();
        assert!(
            claude["hookSpecificOutput"]["updatedInput"]["command"]
                .as_str()
                .unwrap()
                .ends_with("run -- git log -3")
        );
        assert_eq!(
            format_exe_for_shell(
                Path::new("C:/Program Files/footnote/footnote.exe"),
                Shell::PowerShell
            ),
            "& \"C:/Program Files/footnote/footnote.exe\""
        );
    }

    #[test]
    fn classifies_all_five_core_families() {
        let v = |s: &str| s.split(' ').map(String::from).collect::<Vec<_>>();
        assert_eq!(
            classify_command(&v("cargo test --workspace")),
            CommandFamily::CargoTest
        );
        assert_eq!(
            classify_command(&v("cargo clippy --all-targets")),
            CommandFamily::CargoBuild
        );
        assert_eq!(classify_command(&v("pytest -q")), CommandFamily::TestRunner);
        assert_eq!(
            classify_command(&v("node --test a.test.js")),
            CommandFamily::TestRunner
        );
        assert_eq!(classify_command(&v("git status")), CommandFamily::Git);
        assert_eq!(classify_command(&v("git diff")), CommandFamily::Git);
        assert_eq!(classify_command(&v("rg TODO src")), CommandFamily::Search);
        assert_eq!(classify_command(&v("git grep foo")), CommandFamily::Search);
        assert_eq!(classify_command(&v("ruff check .")), CommandFamily::Linter);
        assert_eq!(classify_command(&v("tsc --noEmit")), CommandFamily::Linter);
    }

    #[test]
    fn rewrite_command_skips_pipes_redirects_chains_and_footnote() {
        assert_eq!(
            rewrite_command("cargo test --workspace").as_deref(),
            Some("footnote run -- cargo test --workspace")
        );
        assert_eq!(
            rewrite_command("git status").as_deref(),
            Some("footnote run -- git status")
        );
        assert_eq!(rewrite_command("rg foo src | sort"), None);
        assert_eq!(rewrite_command("cargo test > out.txt"), None);
        assert_eq!(rewrite_command("footnote run -- cargo test"), None);
        assert_eq!(rewrite_command("rtk cargo test"), None);
        assert_eq!(rewrite_command("echo $(whoami)"), None);
        assert_eq!(rewrite_command("env"), None);
    }

    /// #565: agents send compound lines; each filtered part is wrapped and every other byte is kept.
    #[test]
    fn rewrite_command_wraps_each_filtered_part_of_a_compound_line() {
        let cases: &[(&str, Option<&str>)] = &[
            // Bash, as Claude Code writes it.
            (
                "cd D:/x && cargo test --test mcp 2>&1 | head -40",
                Some("cd D:/x && footnote run -- cargo test --test mcp 2>&1 | head -40"),
            ),
            (
                "git status && git diff",
                Some("footnote run -- git status && footnote run -- git diff"),
            ),
            (
                "cargo fmt --check && cargo test --test lean_d2 && git status -s",
                Some(
                    "footnote run -- cargo fmt --check && footnote run -- cargo test --test lean_d2 && footnote run -- git status -s",
                ),
            ),
            (
                "rg -n \"fn tag\" crates | head -20",
                Some("footnote run -- rg -n \"fn tag\" crates | head -20"),
            ),
            (
                "RUST_LOG=debug cargo test",
                Some("RUST_LOG=debug footnote run -- cargo test"),
            ),
            (
                "cargo test 2>&1 || echo failed",
                Some("footnote run -- cargo test 2>&1 || echo failed"),
            ),
            // PowerShell, as Antigravity and Codex write it.
            (
                "Set-Location D:\\x; rg -n foo src",
                Some("Set-Location D:\\x; footnote run -- rg -n foo src"),
            ),
            (
                "$env:RUSTC_WRAPPER = ''\ncargo fmt --all &&\ncargo test --test mcp",
                Some(
                    "$env:RUSTC_WRAPPER = ''\nfootnote run -- cargo fmt --all &&\nfootnote run -- cargo test --test mcp",
                ),
            ),
            (
                "git diff --stat | Select-Object -First 20",
                Some("footnote run -- git diff --stat | Select-Object -First 20"),
            ),
            (
                "Write-Host \"=== a; b ===\"; git log --oneline -3",
                Some("Write-Host \"=== a; b ===\"; footnote run -- git log --oneline -3"),
            ),
            // Separators inside quotes and comments are not separators.
            ("echo \"a && cargo test\"", None),
            (
                "git commit -m \"a && cargo test\"",
                Some("footnote run -- git commit -m \"a && cargo test\""),
            ),
            ("echo 'x; cargo test'", None),
            ("# cargo test; git status\necho hi", None),
            // Output that goes somewhere a filter would change is left alone.
            ("cargo test | grep FAILED", None),
            (
                "git diff > patch.txt && git status",
                Some("git diff > patch.txt && footnote run -- git status"),
            ),
            ("cargo test >&2", None),
            ("cargo test &> log.txt", None),
            ("git log | wc -l", None),
            // `footnote run` ends with a note line, which `tail` and `-Last` would return instead of the program's.
            (
                "cargo test 2>&1 | tail -5",
                Some("footnote run --no-footer -- cargo test 2>&1 | tail -5"),
            ),
            (
                "git log --oneline | Select-Object -Last 3",
                Some("footnote run --no-footer -- git log --oneline | Select-Object -Last 3"),
            ),
            ("cargo test 2>&1 | tail -n +5", None),
            ("cargo test 2>&1 | tail -f", None),
            // Global options before the subcommand.
            (
                "git -C D:/x status --short",
                Some("footnote run -- git -C D:/x status --short"),
            ),
            (
                "cargo +nightly test -p core",
                Some("footnote run -- cargo +nightly test -p core"),
            ),
            (
                "git -C D:/x fetch -q origin",
                Some("footnote run -- git -C D:/x fetch -q origin"),
            ),
            // Stderr sent elsewhere stays out of the filtered output and goes where the agent sent it.
            (
                "git diff --nope 2>/dev/null && echo ok",
                Some("footnote run --raw-stderr -- git diff --nope 2>/dev/null && echo ok"),
            ),
            (
                "git status 2>$null",
                Some("footnote run --raw-stderr -- git status 2>$null"),
            ),
            (
                "ls docs 2>/dev/null | tail -3",
                Some("footnote run --no-footer --raw-stderr -- ls docs 2>/dev/null | tail -3"),
            ),
            // A part with a group is left alone; the parts around it are still rewritten.
            (
                "cd x && cargo build; echo \"$?\" && (cd y && cargo test); git status",
                Some(
                    "cd x && footnote run -- cargo build; echo \"$?\" && (cd y && cargo test); footnote run -- git status",
                ),
            ),
            (
                "if ($LASTEXITCODE -eq 0) { cargo test }\ngit push -q origin main",
                Some(
                    "if ($LASTEXITCODE -eq 0) { cargo test }\nfootnote run -- git push -q origin main",
                ),
            ),
            (
                "for f in a b; do git show $f; done",
                Some("for f in a b; do footnote run -- git show $f; done"),
            ),
            (
                "if cargo test; then git push; fi",
                Some("if footnote run -- cargo test; then footnote run -- git push; fi"),
            ),
            (
                "wc -l < x.txt && git status",
                Some("wc -l < x.txt && footnote run -- git status"),
            ),
            // A loop whose output is piped or redirected carries its body's output there.
            ("for f in a b; do git show $f; done | grep x", None),
            ("for f in a b; do git show $f; done > all.txt", None),
            // Commands that wait on the user or keep running.
            ("git commit", None),
            ("git rebase -i HEAD~3", None),
            ("git add -p", None),
            (
                "git commit -qam \"x\" && git push",
                Some("footnote run -- git commit -qam \"x\" && footnote run -- git push"),
            ),
            ("npx vite --port 5391", None),
            ("npm run dev", None),
            ("docker logs -f api", None),
            (
                "npx -y wrangler@4 deploy --dry-run 2>&1",
                Some("footnote run -- npx -y wrangler@4 deploy --dry-run 2>&1"),
            ),
            (
                "npm ci && npx tauri build",
                Some("footnote run -- npm ci && footnote run -- npx tauri build"),
            ),
            ("gh api repos/o/r -q .name", None),
            ("gh pr checks 12", Some("footnote run -- gh pr checks 12")),
            // Constructs whose separators cannot be found safely leave the whole line alone.
            ("cat <<'EOF' | cargo test\nx\nEOF", None),
            ("for f in a b; do (cd $f && cargo test); done", None),
            ("if (Test-Path x) { cargo test }", None),
            ("case $x in a) cargo test;; esac", None),
            ("cargo test & git status", None),
            ("echo \"$(git status)\" && cargo test", None),
            ("git status `\n && cargo test", None),
            ("$out = @'\ncargo test\n'@", None),
            ("echo \"unclosed && cargo test", None),
            ("cd x && ls -la", Some("cd x && footnote run -- ls -la")),
            // Nothing filtered at all.
            ("cd x && pwd", None),
            ("& \"C:\\tools\\x.exe\" --help; Write-Output done", None),
        ];
        for (cmd, want) in cases {
            assert_eq!(rewrite_command(cmd).as_deref(), *want, "{cmd:?}");
            // Only insertions: removing every `footnote run -- ` gives back the original line.
            if let Some(w) = want {
                let back = w
                    .replace("footnote run --no-footer --raw-stderr -- ", "")
                    .replace("footnote run --no-footer -- ", "")
                    .replace("footnote run --raw-stderr -- ", "")
                    .replace("footnote run -- ", "");
                assert_eq!(back, cmd.trim(), "{cmd:?}");
            }
        }
        // In PowerShell `ls` is `Get-ChildItem`, and bash keywords are not keywords.
        assert_eq!(
            rewrite_command_in("cd x; ls", "footnote", Shell::PowerShell),
            None
        );
        assert_eq!(
            rewrite_command_in("Set-Location x; git status", "footnote", Shell::PowerShell)
                .as_deref(),
            Some("Set-Location x; footnote run -- git status")
        );
    }

    #[test]
    fn listing_keeps_names_sizes_and_kinds_and_drops_the_other_columns() {
        let raw = "total 48\n\
drwxr-xr-x 1 johan 197609     0 Nov 23 10:31 ./\n\
drwxr-xr-x 1 johan 197609     0 Nov 22 09:00 ../\n\
-rw-r--r-- 1 johan 197609  2150 Nov 23 10:31 Cargo.toml\n\
drwxr-xr-x 1 johan 197609     0 Nov 23 10:31 src\n\
-rwxr-xr-x 1 johan 197609 91234 Nov  2  2025 build tool.sh\n\
lrwxrwxrwx 1 johan 197609     7 Nov 23 10:31 latest -> v0.5.0\n";
        assert_eq!(
            filter_listing(raw, false),
            "Cargo.toml  2.1K\nsrc/\nbuild tool.sh*  89.1K\nlatest -> v0.5.0\n"
        );
        let iso = "-rw-r--r-- 1 j 1 512 2026-11-23 10:31:07.123456789 +0100 a.txt\n";
        assert_eq!(
            filter_listing(iso, true),
            "2026-11-23 10:31:07.123456789 +0100  a.txt  512\n"
        );
        // Plain `ls` and `ls -R` headers pass through.
        assert_eq!(
            filter_listing("a\nb\n\nsrc:\nc\n", false),
            "a\nb\n\nsrc:\nc\n"
        );
    }

    #[test]
    fn git_drops_transfer_noise_and_collapses_line_ending_warnings() {
        let push = "Enumerating objects: 9, done.\nCounting objects: 100% (9/9), done.\n\
Writing objects: 100% (5/5), 1.2 KiB | 1.2 MiB/s, done.\nTotal 5 (delta 4), reused 0 (delta 0)\n\
remote: Resolving deltas: 100% (4/4)\nremote:\nremote: Create a pull request for 'x' on GitHub by visiting:\n\
remote:      https://github.com/o/r/pull/new/x\nremote:\nTo github.com:o/r.git\n * [new branch]      x -> x\n\
hint: use --set-upstream\nremote: error: GH006: Protected branch update failed\n";
        assert_eq!(
            filter_git(Some("push"), push),
            "To github.com:o/r.git\n * [new branch]      x -> x\nremote: error: GH006: Protected branch update failed\n"
        );
        let add = "warning: in the working copy of 'a.rs', LF will be replaced by CRLF the next time Git touches it\n\
warning: in the working copy of 'b.rs', LF will be replaced by CRLF the next time Git touches it\n\
warning: in the working copy of 'c.rs', LF will be replaced by CRLF the next time Git touches it\n";
        assert_eq!(
            filter_git(Some("add"), add).trim_end(),
            "warning: Git will change line endings in 3 files the next time it touches them: a.rs, b.rs, c.rs"
        );
    }

    #[test]
    fn secret_detector_catches_common_credentials_and_ignores_benign_logs() {
        assert!(contains_secrets("AWS_ACCESS_KEY_ID=AKIAIOSFODNN7EXAMPLE"));
        assert!(contains_secrets(
            "token ghp_1234567890abcdef1234567890abcdef"
        ));
        assert!(contains_secrets(
            "Authorization: Bearer eyJhbGciOiJIUzI1NiJ9.abcdef12345.sig12345678"
        ));
        assert!(contains_secrets("-----BEGIN OPENSSH PRIVATE KEY-----\nabc"));
        assert!(contains_secrets(
            "postgres://admin:supersecret99@db.example.com/app"
        ));
        assert!(contains_secrets(
            "api_key = \"sk-ant-api03-abcdefghijklmnopqrstuvwx\""
        ));
        assert!(!contains_secrets(
            "test result: ok. 42 passed; 0 failed; 0 ignored;"
        ));
        assert!(!contains_secrets(
            "error[E0308]: mismatched types\n --> src/main.rs:10:5"
        ));
    }

    #[test]
    fn cargo_test_preserves_failure_blocks_and_shrinks_passing_noise() {
        let mut raw = String::new();
        for i in 0..40 {
            raw.push_str(&format!("   Compiling crate-{i} v0.1.0\n"));
        }
        raw.push_str("    Finished `test` profile in 2.1s\n     Running unittests src/lib.rs\n\nrunning 30 tests\n");
        for i in 0..29 {
            raw.push_str(&format!("test suite::case_{i} ... ok\n"));
        }
        raw.push_str("test suite::broken_case ... FAILED\n\nfailures:\n\n---- suite::broken_case stdout ----\nthread 'suite::broken_case' panicked at src/lib.rs:42:9:\nassertion `left == right` failed\n  left: 1\n right: 2\n\nfailures:\n    suite::broken_case\n\ntest result: FAILED. 29 passed; 1 failed; 0 ignored; 0 measured; 0 filtered out\n");

        let out = filter_output(CommandFamily::CargoTest, Some("test"), &raw);
        assert!(
            out.len() < raw.len() / 2,
            "expected >50% shrink: {} vs {}",
            out.len(),
            raw.len()
        );
        assert!(out.contains("suite::broken_case ... FAILED"));
        assert!(out.contains("panicked at src/lib.rs:42:9"));
        assert!(out.contains("left: 1"));
        assert!(out.contains("right: 2"));
        assert!(out.contains("29 passed; 1 failed"));
    }

    #[test]
    fn git_status_keeps_untracked_files_and_drops_the_closing_hint() {
        let raw = "On branch main
Changes not staged for commit:
  (use \"git add <file>...\" to update what will be committed)
	modified:   src/run.rs

Untracked files:
  (use \"git add <file>...\" to include in what will be committed)
	notes.md

no changes added to commit (use \"git add\" and/or \"git commit -a\")
";
        let out = filter_output(CommandFamily::Git, Some("status"), raw);
        assert_eq!(
            out,
            "On branch main
 M src/run.rs
?? notes.md",
            "{out}"
        );
    }

    #[test]
    fn search_groups_by_file_preserving_every_line_and_match() {
        let raw = "crates/search/src/semantic.rs:10:fn alpha() {}\ncrates/search/src/semantic.rs:20:fn beta() {}\ncrates/search/src/semantic.rs:30:fn gamma() {}\ncrates/search/src/store.rs:5:fn open() {}\n";
        let out = filter_output(CommandFamily::Search, None, raw);
        assert!(out.len() < raw.len());
        assert!(out.contains("crates/search/src/semantic.rs:\n  10:fn alpha() {}\n  20:fn beta() {}\n  30:fn gamma() {}"));
        assert!(out.contains("crates/search/src/store.rs:\n  5:fn open() {}"));
    }

    #[test]
    fn git_diff_preserves_hunks_edits_and_adjacent_anchors() {
        let raw = "diff --git a/src/a.rs b/src/a.rs\nindex 1111111..2222222 100644\n--- a/src/a.rs\n+++ b/src/a.rs\n@@ -1,9 +1,9 @@\n ctx1\n ctx2\n ctx3\n anchor_before\n-old_line\n+new_line\n anchor_after\n ctx4\n ctx5\n";
        let out = filter_output(CommandFamily::Git, Some("diff"), raw);
        assert!(out.len() < raw.len());
        assert!(out.contains("@@ -1,9 +1,9 @@"));
        assert!(out.contains(" anchor_before"));
        assert!(out.contains("-old_line"));
        assert!(out.contains("+new_line"));
        assert!(out.contains(" anchor_after"));
        assert!(!out.contains("index 1111111..2222222"));
        assert!(!out.contains("ctx1"));
    }

    #[test]
    fn handle_id_validation_rejects_traversal() {
        assert!(validate_handle_id("h-0123456789ab").is_ok());
        assert!(validate_handle_id("../memory").is_err());
        assert!(validate_handle_id("h-../../etc/passwd").is_err());
        assert!(validate_handle_id("memory.db").is_err());
    }
}
