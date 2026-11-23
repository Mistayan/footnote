# Footnote One installer for Windows

`Footnote-Setup-<version>-x64.exe` installs the engine (`footnote.exe`) and the tray launcher (`footnote-launcher.exe`) for the
current user in `%LOCALAPPDATA%\Programs\footnote`. It needs no administrator rights.

## What it does

- Start menu shortcut **Footnote**.
- Options on the "Select Additional Tasks" page:
  - **Start Footnote with Windows, in the tray**: on by default. Adds `footnote-launcher.exe --tray` to your startup programs
    (`HKCU\...\Run`), so the Footnote icon sits in the notification area after you sign in.
  - **Create a desktop shortcut**: off by default.
  - **Add footnote to PATH**: on by default, so terminals and agents can run `footnote`.
  - **Connect the coding agents found on this computer now**: off by default. Runs `footnote install` (Memory and Lean hooks,
    MCP server) for Claude Code, Codex, Antigravity CLI (`agy`) and the others it finds. You can do it later from a terminal.
- Upgrading over a running Footnote is safe: a `footnote.exe` your agents still use is renamed aside
  (`footnote.exe.replaced-<time>`), the way `footnote update` does it, instead of being closed.

The engine links against the Microsoft Visual C++ runtime (with OpenMP). Its redistributable DLLs (`vcruntime140`,
`vcruntime140_1`, `msvcp140`, `msvcp140_1`, `vcomp140`) are installed beside `footnote.exe` (app-local deployment, allowed by
the Visual Studio redistribution terms), so Footnote runs on a fresh Windows without the VC++ Redistributable.

Your data (memories, indexes, settings) lives in Footnote's state folder, apart from the program. Neither an upgrade nor an
uninstall touches it. Uninstalling first runs `footnote uninstall --memory --lean`, so your agents' hooks do not point at a
missing program.

## The installer is not signed

Footnote is a single-maintainer open-source project and ships unsigned (decided 21 Nov 2026, #125). Windows SmartScreen will
say "Windows protected your PC". To continue: **More info**, then **Run anyway**. Check the file first against `sha256.sum` in
the release:

```powershell
(Get-FileHash .\Footnote-Setup-<version>-x64.exe -Algorithm SHA256).Hash
```

Where a company's Windows Application Control blocks unsigned programs, use the Docker image instead (#392).

## Silent install

```powershell
.\Footnote-Setup-<version>-x64.exe /VERYSILENT /SUPPRESSMSGBOXES /TASKS="startup,addtopath"
```

Add `desktopicon` or `agents` to `/TASKS` to turn those on. Uninstall: Settings > Apps > Footnote One, or
`"%LOCALAPPDATA%\Programs\footnote\unins000.exe" /VERYSILENT`.

## Build

Needs Inno Setup 6.7 (`winget install JRSoftware.InnoSetup`), a release `footnote.exe` and a release `footnote-launcher.exe`
(`npx tauri build --no-bundle` in `apps/launcher`).

```powershell
ISCC /DAppVersion=0.1.0-alpha.3 /DEngine=C:\path\footnote.exe /DLauncher=C:\path\footnote-launcher.exe installer\footnote.iss
```

The release workflow builds it on every tagged release and attaches it with its SHA-256 (`.github/workflows/installer.yml`).
