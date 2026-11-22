//! Footnote One's window. It draws from the `footnote` engine, run as a child process for each read: the window holds no
//! data of its own and can only run the commands in `allowed`: reads, turning a product on or off, and installing a model
//! (the one network step, started by a click, cancellable).
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use serde_json::Value;
use std::path::PathBuf;
use std::process::{Child, Command, Stdio};
use std::sync::Mutex;

/// The model download in progress, so `cancel_install` can stop it.
static INSTALL: Mutex<Option<Child>> = Mutex::new(None);
use tauri::Manager;
use tauri::menu::{Menu, MenuItem};
use tauri::tray::{MouseButton, MouseButtonState, TrayIconBuilder, TrayIconEvent};

/// A skill or project name as an argument: never an option, no control characters, bounded.
fn plain(s: &str) -> bool {
    !s.is_empty() && s.len() <= 200 && !s.starts_with('-') && !s.chars().any(char::is_control)
}

/// A valid catalogue model name: lowercase ASCII, digits, dashes.
fn model_name(s: &str) -> bool {
    !s.is_empty()
        && s.len() <= 64
        && !s.starts_with('-')
        && s.chars()
            .all(|c| c.is_ascii_lowercase() || c.is_ascii_digit() || c == '-')
}

/// The engine commands the window may run: read-only ones and a few reversible writes: a product's on/off switch, the
/// skill-rewriting switch (a company policy still wins, enforced by the engine), approving or refusing an agent's
/// pending skill change, switching installed models, browsing/forgetting memories, and managing corpora.
fn allowed(args: &[String]) -> bool {
    let a: Vec<&str> = args.iter().map(String::as_str).collect();
    match a.as_slice() {
        ["status"]
        | ["projects"]
        | ["projects", "--quick"]
        | ["activity"]
        | ["jobs"]
        | ["gain"]
        | ["models", "list"]
        | ["corpora"]
        | ["docs", "list"]
        | ["memory-list"] => true,
        ["code", name, "--root", _] => !name.starts_with('-'),
        ["activity" | "usage" | "gain", "--days", d] => d.parse::<u16>().is_ok(),
        ["usage", "--days", d, "--sync-prices"] => d.parse::<u16>().is_ok(),
        ["code-map", "--root", _] => true,
        // Parser graph of one project (no `--deep`, so no project code runs). The engine refuses a missing folder.
        ["code-index", root] => plain(root),
        // The impact radius before a change: a read, like `code`.
        ["code-impact", name, "--root", _] => !name.starts_with('-'),
        // The query follows `--`, so text starting with a dash is never read as an option.
        ["find", "--", q] => !q.trim().is_empty() && q.chars().count() <= 500,
        // One model by its catalogue name; the engine refuses names it does not know.
        ["models", "install", name] => model_name(name),
        // Switch which installed models Memory uses (1 to 3 valid catalogue names).
        ["models", "use", m1] => model_name(m1),
        ["models", "use", m1, m2] => model_name(m1) && model_name(m2),
        ["models", "use", m1, m2, m3] => model_name(m1) && model_name(m2) && model_name(m3),
        // Browse memories and forget one by numeric id from the Memory screen.
        ["memory-list", "--limit", l, "--offset", o] => {
            l.parse::<usize>().is_ok() && o.parse::<usize>().is_ok()
        }
        ["memory-list", "--project", p, "--limit", l, "--offset", o] => {
            plain(p) && l.parse::<usize>().is_ok() && o.parse::<usize>().is_ok()
        }
        ["memory-list", "--kind", k, "--limit", l, "--offset", o] => {
            plain(k) && l.parse::<usize>().is_ok() && o.parse::<usize>().is_ok()
        }
        [
            "memory-list",
            "--project",
            p,
            "--kind",
            k,
            "--limit",
            l,
            "--offset",
            o,
        ] => plain(p) && plain(k) && l.parse::<usize>().is_ok() && o.parse::<usize>().is_ok(),
        // Forget rejects a pending global preference (#207); memory-restore approves it.
        ["forget" | "memory-restore", id] => id.parse::<i64>().is_ok(),
        // Remove a corpus registration from Library (never deletes the database file on disk).
        ["corpora", "remove", p] => {
            !p.is_empty() && !p.starts_with('-') && !p.chars().any(char::is_control)
        }
        [
            "config",
            "set",
            "memory.enabled" | "library.enabled" | "code.enabled" | "memory.skill_rewrite",
            "true" | "false",
        ] => true,
        // The options catalogue (what each option gains and costs) and the review queue: reads.
        ["options"] | ["memory-review"] => true,
        // An agent's pending change to a skill's scripts: the user reads its diff (#472), then serves or refuses it (#457).
        // Nothing runs it.
        ["skills", "approve" | "reject" | "diff", name] => plain(name),
        [
            "skills",
            "approve" | "reject" | "diff",
            name,
            "--project",
            project,
        ] => plain(name) && plain(project),
        ["code-map", "--root", _, "--depth", d] => d.parse::<u8>().is_ok(),
        // One block's files (#504): a folder path from the map, nothing else.
        ["code-map", "--root", _, "--block", b] => {
            plain(b) && b.chars().all(|c| c.is_alphanumeric() || "/\\._- ".contains(c))
        }
        // The commit button (22 Nov 2026): queue or withdraw the engine's fixed commit-and-push request for the next agent
        // turn in a project. The window names the project only; the text is the engine's.
        ["agent-ask", project] | ["agent-ask", project, "--cancel"] => plain(project),
        // The commit button: the agent last used in the project commits and pushes now, unattended, with the engine's fixed
        // request (Claude Code may run git only).
        ["agent-commit", project] => plain(project),
        // The Projects screen's Ignore button and its undo: Footnote stops listing and recording a project (22 Nov 2026).
        ["projects", "ignore" | "unignore", project] => plain(project),
        // Add project: the folder the user picked in the window's folder browser.
        ["projects", "add", folder] => plain(folder),
        // Options (22 Nov 2026): compare with the latest GitHub release, fetch and verify its installer (run by
        // `install_update`, never by the page), and reconnect the agents whose hooks or MCP server are missing.
        ["update", "--check"] | ["update", "--download"] => true,
        ["install", "--memory"] => true,
        _ => false,
    }
}

/// Where the engine is: `FOOTNOTE_BIN`, beside this app, the per-user install folder on Windows, then PATH.
fn engine() -> PathBuf {
    if let Some(p) = std::env::var_os("FOOTNOTE_BIN") {
        return p.into();
    }
    let exe = if cfg!(windows) {
        "footnote.exe"
    } else {
        "footnote"
    };
    let beside = std::env::current_exe()
        .ok()
        .and_then(|p| p.parent().map(|d| d.join(exe)));
    let installed = std::env::var_os("LOCALAPPDATA")
        .map(|l| PathBuf::from(l).join("Programs").join("footnote").join(exe));
    [beside, installed.filter(|_| cfg!(windows))]
        .into_iter()
        .flatten()
        .find(|p| p.is_file())
        .unwrap_or_else(|| exe.into())
}

/// Run one allowed engine command and return its JSON. Errors are the engine's own message, or `ENGINE_MISSING`.
#[tauri::command(async)]
fn footnote(args: Vec<String>) -> Result<Value, String> {
    if !allowed(&args) {
        return Err(format!(
            "not allowed from the window: footnote {}",
            args.join(" ")
        ));
    }
    let mut cmd = Command::new(engine());
    cmd.args(&args);
    #[cfg(windows)]
    {
        use std::os::windows::process::CommandExt;
        cmd.creation_flags(0x0800_0000); // CREATE_NO_WINDOW: no console flashes over the app
    }
    let missing = |e: std::io::Error| match e.kind() {
        std::io::ErrorKind::NotFound => "ENGINE_MISSING".to_string(),
        _ => e.to_string(),
    };
    let out = if args.first().is_some_and(|a| a == "models")
        && args.get(1).is_some_and(|a| a == "install")
    {
        install(cmd).map_err(missing)?
    } else {
        cmd.output().map_err(missing)?
    };
    let json: Value = serde_json::from_slice(&out.stdout)
        .map_err(|_| String::from_utf8_lossy(&out.stderr).trim().to_string())?;
    match json.get("error").and_then(Value::as_str) {
        Some(e) => Err(e.to_string()),
        None if !out.status.success() => {
            Err(String::from_utf8_lossy(&out.stderr).trim().to_string())
        }
        None => Ok(json),
    }
}

/// Run a model install so it can be cancelled: the child stays in `INSTALL` while it runs. The engine downloads to `.partial`
/// files renamed only when complete and hash-checked, so a cancelled install leaves no model half-installed.
fn install(mut cmd: Command) -> std::io::Result<std::process::Output> {
    let mut child = cmd.stdout(Stdio::piped()).stderr(Stdio::piped()).spawn()?;
    let (out, err) = (
        child.stdout.take().expect("piped"),
        child.stderr.take().expect("piped"),
    );
    let read = |mut r: Box<dyn std::io::Read + Send>| {
        std::thread::spawn(move || {
            let mut b = Vec::new();
            let _ = r.read_to_end(&mut b);
            b
        })
    };
    let (read_out, read_err) = (read(Box::new(out)), read(Box::new(err)));
    *INSTALL.lock().unwrap_or_else(|p| p.into_inner()) = Some(child);
    let status = loop {
        let mut slot = INSTALL.lock().unwrap_or_else(|p| p.into_inner());
        match slot.as_mut().map(Child::try_wait) {
            Some(Ok(Some(status))) => {
                *slot = None;
                break status;
            }
            Some(Ok(None)) => {}
            Some(Err(e)) => {
                *slot = None;
                return Err(e);
            }
            None => return Err(std::io::Error::other("cancelled")),
        }
        drop(slot);
        std::thread::sleep(std::time::Duration::from_millis(200));
    };
    Ok(std::process::Output {
        status,
        stdout: read_out.join().unwrap_or_default(),
        stderr: read_err.join().unwrap_or_default(),
    })
}

/// Open a web address or a folder in the system browser, mail app or file manager, outside the window.
fn open_outside(target: &std::ffi::OsStr) -> Result<(), String> {
    #[cfg(windows)]
    let mut cmd = std::process::Command::new("explorer.exe");
    #[cfg(target_os = "macos")]
    let mut cmd = std::process::Command::new("open");
    #[cfg(all(unix, not(target_os = "macos")))]
    let mut cmd = std::process::Command::new("xdg-open");
    // explorer.exe returns 1 even when it opened the target, so only a failed start counts.
    cmd.arg(target).spawn().map(drop).map_err(|e| e.to_string())
}

/// The support links: only these fixed addresses can be opened (decided 17 Nov; the install page added for #472).
#[tauri::command]
fn open_support(to: String) -> Result<(), String> {
    let url = match to.as_str() {
        "issues" => "https://github.com/bobcat88/footnote/issues/new",
        "install" => "https://github.com/bobcat88/footnote/releases/latest",
        "email" => "mailto:johan.velocity.lab@pm.me?subject=Footnote",
        "litellm" => "https://models.litellm.ai",
        // The licence texts the Models screen explains (22 Nov 2026).
        "license:mit" => "https://opensource.org/license/mit",
        "license:apache-2.0" => "https://www.apache.org/licenses/LICENSE-2.0",
        "license:cc-by-nc-4.0" => "https://creativecommons.org/licenses/by-nc/4.0/",
        _ => return Err("unknown support address".into()),
    };
    open_outside(url.as_ref())
}

/// A measurement report the catalogue cites (`bench/experiments/<name>.md`), as its page on the project's site. Anything
/// else (another folder, `..`, a query or a scheme) gives `None`.
fn receipt_url(path: &str) -> Option<String> {
    let name = path.strip_prefix("bench/experiments/")?;
    let ok = name.len() <= 100
        && name.ends_with(".md")
        && !name.starts_with('.')
        && name
            .chars()
            .all(|c| c.is_ascii_alphanumeric() || matches!(c, '-' | '_' | '.'));
    ok.then(|| format!("https://github.com/bobcat88/footnote/blob/main/{path}"))
}

/// Open the measurement behind an option's cost (#472), on the project's site.
#[tauri::command]
fn open_receipt(path: String) -> Result<(), String> {
    let url = receipt_url(&path).ok_or("not a measurement report")?;
    open_outside(url.as_ref())
}

/// Open the folder holding an agent's pending skill change, so the user can read its files before approving (#472). The
/// window names the skill only: the folder comes from the engine's `skills diff`, never from the page.
#[tauri::command(async)]
fn open_skill_folder(name: String, project: Option<String>) -> Result<(), String> {
    let mut args = vec!["skills".to_string(), "diff".into(), name];
    if let Some(p) = project {
        args.extend(["--project".into(), p]);
    }
    let diff = footnote(args)?;
    let folder = PathBuf::from(
        diff["folder"]
            .as_str()
            .ok_or("the engine named no folder")?,
    );
    if !folder.is_dir() {
        return Err(format!("{} is not a folder", folder.display()));
    }
    open_outside(folder.as_os_str())
}

/// Open a project's folder in the file manager (the Projects screen, 22 Nov 2026). Only a folder the engine's own project
/// list names opens, so the page cannot open an arbitrary path.
#[tauri::command(async)]
fn open_project_folder(path: String) -> Result<(), String> {
    // Names and folders only: the full list reads git in every project, which the click does not need.
    let projects = footnote(vec!["projects".into(), "--quick".into()])?;
    let known = projects["projects"]
        .as_array()
        .is_some_and(|list| list.iter().any(|p| p["path"].as_str() == Some(path.as_str())));
    if !known {
        return Err("not a Footnote project".into());
    }
    let folder = PathBuf::from(&path);
    if !folder.is_dir() {
        return Err(format!("{} is not a folder", folder.display()));
    }
    open_outside(folder.as_os_str())
}

/// Restart to update (22 Nov 2026): the page has already had the engine download and verify the installer
/// (`update --download`), so asking again returns the same verified file at once. This runs it with no window at all,
/// closes Footnote so its files can be replaced (the installer also stops the launcher and sets aside a `footnote.exe` an
/// agent still runs), and starts Footnote again when the installer is done. The path comes from the engine, never from
/// the page.
#[tauri::command(async)]
fn install_update(app: tauri::AppHandle) -> Result<Value, String> {
    let got = footnote(vec!["update".into(), "--download".into()])?;
    if got["up_to_date"] == true {
        return Ok(got);
    }
    let installer = PathBuf::from(got["installer"].as_str().ok_or("the engine named no installer")?);
    let name = installer
        .file_name()
        .map(|n| n.to_string_lossy().into_owned())
        .unwrap_or_default();
    let in_updates = installer
        .parent()
        .and_then(|d| d.file_name())
        .is_some_and(|d| d == "updates");
    if !(installer.is_file() && in_updates && name.starts_with("Footnote-Setup-") && name.ends_with("-x64.exe")) {
        return Err(format!("not a Footnote installer: {}", installer.display()));
    }
    run_installer(&installer)?;
    // Leave a moment for the reply to reach the page, then free the launcher's files for the installer.
    std::thread::spawn(move || {
        std::thread::sleep(std::time::Duration::from_millis(600));
        app.exit(0);
    });
    Ok(got)
}

#[cfg(windows)]
fn run_installer(installer: &std::path::Path) -> Result<(), String> {
    use std::os::windows::process::CommandExt;
    const CREATE_NO_WINDOW: u32 = 0x0800_0000;
    let me = std::env::current_exe().map_err(|e| e.to_string())?;
    Command::new("cmd.exe")
        .raw_arg(format!(
            "/C start \"\" /wait \"{}\" /VERYSILENT /SUPPRESSMSGBOXES /NORESTART & start \"\" \"{}\"",
            installer.display(),
            me.display()
        ))
        .creation_flags(CREATE_NO_WINDOW)
        .spawn()
        .map(drop)
        .map_err(|e| e.to_string())
}

#[cfg(not(windows))]
fn run_installer(_: &std::path::Path) -> Result<(), String> {
    Err("in-app updates install the Windows installer; elsewhere run footnote-installer.sh".into())
}

/// One level of the Add project folder browser (22 Nov 2026): the drives, or a folder's subfolders by name with whether
/// each is a git repository. Names only, nothing is read inside them; hidden and system folders are left out.
#[tauri::command(async)]
fn browse_folders(path: Option<String>) -> Result<Value, String> {
    let drives: Vec<String> = if cfg!(windows) {
        (b'A'..=b'Z')
            .map(|c| format!("{}:/", c as char))
            .filter(|d| std::path::Path::new(d).is_dir())
            .collect()
    } else {
        vec!["/".into()]
    };
    let Some(path) = path.filter(|p| !p.trim().is_empty()) else {
        let home = std::env::var("USERPROFILE").or_else(|_| std::env::var("HOME")).ok();
        return Ok(serde_json::json!({"path": null, "parent": null, "drives": drives, "home": home, "folders": []}));
    };
    let dir = PathBuf::from(&path);
    let entries = std::fs::read_dir(&dir).map_err(|e| format!("{}: {e}", dir.display()))?;
    let mut folders: Vec<Value> = entries
        .flatten()
        .filter(|e| e.file_type().is_ok_and(|t| t.is_dir()))
        .filter(|e| {
            let name = e.file_name().to_string_lossy().into_owned();
            !name.starts_with('.') && !name.starts_with('$') && !hidden(e)
        })
        .take(2000)
        .map(|e| {
            let p = e.path();
            serde_json::json!({
                "name": e.file_name().to_string_lossy(),
                "path": p.to_string_lossy().replace('\\', "/"),
                "git": p.join(".git").exists(),
            })
        })
        .collect();
    folders.sort_by_key(|f| f["name"].as_str().unwrap_or_default().to_lowercase());
    Ok(serde_json::json!({
        "path": dir.to_string_lossy().replace('\\', "/"),
        "parent": dir.parent().map(|p| p.to_string_lossy().replace('\\', "/")),
        "git": dir.join(".git").exists(),
        "drives": drives,
        "folders": folders,
    }))
}

#[cfg(windows)]
fn hidden(e: &std::fs::DirEntry) -> bool {
    use std::os::windows::fs::MetadataExt;
    const HIDDEN: u32 = 0x2;
    const SYSTEM: u32 = 0x4;
    e.metadata().is_ok_and(|m| m.file_attributes() & (HIDDEN | SYSTEM) != 0)
}

#[cfg(not(windows))]
fn hidden(_: &std::fs::DirEntry) -> bool {
    false
}

/// Stop the model download in progress, if any. Returns whether one was running.
#[tauri::command]
fn cancel_install() -> bool {
    let child = INSTALL.lock().unwrap_or_else(|p| p.into_inner()).take();
    child.is_some_and(|mut c| {
        let _ = c.kill();
        let _ = c.wait();
        true
    })
}

/// Show one of the two windows and hide the other, as the in-app switch does: one Footnote window at a time.
fn show(app: &tauri::AppHandle, label: &str) {
    let other = if label == "main" { "mini" } else { "main" };
    if let Some(w) = app.get_webview_window(other) {
        let _ = w.hide();
    }
    if let Some(w) = app.get_webview_window(label) {
        let _ = w.unminimize();
        let _ = w.show();
        let _ = w.set_focus();
    }
}

/// `--tray`: start in the tray without opening a window. The installer's Windows startup entry passes it.
fn tray_only(args: &[String]) -> bool {
    args.iter().any(|a| a == "--tray")
}

fn main() {
    tauri::Builder::default()
        // One Footnote at a time: launching it again (the shortcut, or startup while it runs) opens the running one's window
        // instead of a second tray icon.
        .plugin(tauri_plugin_single_instance::init(|app, args, _cwd| {
            if !tray_only(&args) {
                show(app, "main");
            }
        }))
        .invoke_handler(tauri::generate_handler![
            footnote,
            cancel_install,
            open_support,
            open_skill_folder,
            open_receipt,
            open_project_folder,
            browse_folders,
            install_update
        ])
        // The tray (decided 15 Nov: a compact tray panel plus the full window): a left click opens the mini panel, the menu
        // opens either window or quits. Quitting is only ever from this menu, so closing a window never loses the app.
        .setup(|app| {
            let open = MenuItem::with_id(app, "open", "Open Footnote", true, None::<&str>)?;
            let mini = MenuItem::with_id(app, "mini", "Mini mode", true, None::<&str>)?;
            let quit = MenuItem::with_id(app, "quit", "Quit Footnote", true, None::<&str>)?;
            let mut tray = TrayIconBuilder::with_id("footnote")
                .tooltip("Footnote")
                .menu(&Menu::with_items(app, &[&open, &mini, &quit])?)
                .show_menu_on_left_click(false)
                .on_menu_event(|app, event| match event.id.as_ref() {
                    "open" => show(app, "main"),
                    "mini" => show(app, "mini"),
                    "quit" => app.exit(0),
                    _ => {}
                })
                .on_tray_icon_event(|tray, event| {
                    if let TrayIconEvent::Click {
                        button: MouseButton::Left,
                        button_state: MouseButtonState::Up,
                        ..
                    } = event
                    {
                        show(tray.app_handle(), "mini");
                    }
                });
            if let Some(icon) = app.default_window_icon() {
                tray = tray.icon(icon.clone());
            }
            tray.build(app)?;
            // The main window starts hidden (tauri.conf.json), so a startup launch never flashes it.
            if !tray_only(&std::env::args().collect::<Vec<_>>()) {
                show(app.handle(), "main");
            }
            Ok(())
        })
        // Closing a window hides it; the app stays in the tray until "Quit Footnote".
        .on_window_event(|window, event| {
            if let tauri::WindowEvent::CloseRequested { api, .. } = event {
                api.prevent_close();
                let _ = window.hide();
            }
        })
        .run(tauri::generate_context!())
        .expect("run the Footnote window");
}

#[cfg(test)]
mod tests {
    use super::{allowed, receipt_url, tray_only};

    /// #472: only a report under bench/experiments opens, and only on the project's site.
    #[test]
    fn only_measurement_reports_open_as_receipts() {
        assert_eq!(
            receipt_url("bench/experiments/SKILL-EDIT-COST-2026-11-21.md").as_deref(),
            Some(
                "https://github.com/bobcat88/footnote/blob/main/bench/experiments/SKILL-EDIT-COST-2026-11-21.md"
            )
        );
        for bad in [
            "bench/experiments/../../SECURITY.md",
            "bench/experiments/a/b.md",
            "bench/experiments/x.md?y=1",
            "bench/experiments/.md",
            "bench/experiments/run.sh",
            "https://example.com/bench/experiments/x.md",
            "docs/x.md",
            "",
        ] {
            assert!(receipt_url(bad).is_none(), "{bad}");
        }
    }

    #[test]
    fn tray_flag_starts_without_a_window() {
        let args = |a: &[&str]| a.iter().map(|s| s.to_string()).collect::<Vec<_>>();
        assert!(tray_only(&args(&["footnote-launcher.exe", "--tray"])));
        assert!(!tray_only(&args(&["footnote-launcher.exe"])));
        assert!(!tray_only(&args(&["footnote-launcher.exe", "--trayx"])));
    }

    fn ok(a: &str) -> bool {
        allowed(&a.split(' ').map(String::from).collect::<Vec<_>>())
    }

    #[test]
    fn only_read_commands_pass() {
        assert!(
            ok("status")
                && ok("jobs")
                && ok("models list")
                && ok("code lookup --root D:/p")
                && ok("code-map --root . --depth 2")
        );
        assert!(!ok("jobs --bad"));
        assert!(ok("install --memory") && !ok("install --memory --dry-run") && !ok("install --lean"));
        assert!(!ok("models remove jina-v5-nano") && !ok("uninstall --memory"));
        assert!(ok("update --check") && ok("update --download") && !ok("update --from C:/x.exe") && !ok("rollback"));
        assert!(ok("forget 12") && !ok("forget abc"));
        assert!(ok("agent-ask footnote") && ok("agent-ask footnote --cancel"));
        assert!(ok("agent-commit footnote") && !ok("agent-commit --all") && !ok("agent-commit a b"));
        assert!(ok("projects --quick") && ok("projects ignore scratch") && ok("projects unignore scratch"));
        assert!(ok("projects add D:/work/shop") && !ok("projects add --help") && !ok("projects add a b"));
        assert!(!ok("projects ignore --all") && !ok("projects ignore a b") && !ok("projects forget scratch"));
        assert!(!ok("agent-ask --cancel") && !ok("agent-ask a b") && !ok("agent-ask footnote --text hi"));
        assert!(
            ok("memory-restore 12")
                && !ok("memory-restore 1;x")
                && ok("docs list")
                && !ok("docs add x")
        );
        assert!(ok("code-index D:/x") && !ok("code-index --deep") && !ok("code-index a b"));
        assert!(!ok("code --root . --root") && !ok("code-map --root . --depth 2;rm"));
        assert!(ok("code-map --root . --block crates/code/src") && ok("code-map --root . --block src"));
        assert!(!ok("code-map --root . --block src;rm") && !ok("code-map --root . --block --depth"));
        assert!(!ok("code-map --root . --block src --depth 2"));
        assert!(
            ok("usage --days 30")
                && ok("usage --days 7 --sync-prices")
                && ok("activity --days 7")
                && ok("gain")
                && ok("gain --days 7")
                && !ok("usage --days x")
        );
        assert!(ok("config set code.enabled false") && ok("config set memory.enabled true"));
        assert!(
            ok("models install jina-v5-nano")
                && ok("models use gte-small")
                && ok("models use bekko-a8m gte-small")
                && !ok("models install --all")
                && !ok("models install a b")
                && !ok("models install ../x")
                && !ok("models remove gte-small")
                && !ok("models use ../x")
        );
        assert!(
            ok("find -- daemon") && ok("find -- --db") && !ok("find daemon") && !ok("find -- ")
        );
        assert!(
            !ok("config set memory.resident false")
                && !ok("config set code.enabled maybe")
                && !ok("config set code.enabled")
        );
    }

    /// #457: the Skills screen's reads and writes, and nothing around them.
    #[test]
    fn skill_review_commands_pass_and_nothing_else() {
        assert!(ok("options") && ok("memory-review"));
        assert!(
            ok("config set memory.skill_rewrite true")
                && ok("config set memory.skill_rewrite false")
                && !ok("config set memory.skill_trial_uses 2")
        );
        assert!(
            ok("skills approve css-transitions")
                && ok("skills reject css-transitions --project atlas-api")
                && ok("skills diff css-transitions")
                && ok("skills diff css-transitions --project atlas-api")
                && ok("skills approve plugin:name")
        );
        assert!(
            !ok("skills approve --project x")
                && !ok("skills reject a --project --force")
                && !ok("skills revise a")
                && !ok("skills drop a")
                && !ok("skills approve a b")
                && !ok("skills diff --project x")
                && !ok("memory-review --limit 5")
                && !ok("options --set")
        );
    }
}
