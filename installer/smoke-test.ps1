# Smoke test for the Windows installer (#125): install silently, check what a user would see, then uninstall and check it is
# all gone. CI runs it on a fresh runner (.github/workflows/installer.yml). Locally, -KeepInstalled skips the uninstall, which
# would also take Footnote out of your agents (it runs `footnote uninstall --memory --lean`).
#
#   pwsh installer/smoke-test.ps1 -Setup .\out\Footnote-Setup-<version>-x64.exe [-KeepInstalled]
param(
    [Parameter(Mandatory)] [string] $Setup,
    [switch] $KeepInstalled
)
$ErrorActionPreference = 'Stop'
$app = Join-Path $env:LOCALAPPDATA 'Programs\footnote'
$startMenu = Join-Path $env:APPDATA 'Microsoft\Windows\Start Menu\Programs\Footnote.lnk'
$desktop = Join-Path ([Environment]::GetFolderPath('Desktop')) 'Footnote.lnk'
$runKey = 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Run'
$failures = [System.Collections.Generic.List[string]]::new()

function Check([string] $what, [bool] $ok) {
    if ($ok) { Write-Host "ok    $what" } else { Write-Host "FAIL  $what"; $failures.Add($what) }
}
function RunValue { (Get-ItemProperty $runKey -Name Footnote -ErrorAction SilentlyContinue).Footnote }
function PathEntries { @(((Get-ItemProperty HKCU:\Environment -ErrorAction SilentlyContinue).Path -split ';') | Where-Object { $_ -eq $app }).Count }
function Launchers { @(Get-Process footnote-launcher -ErrorAction SilentlyContinue) }
# Wait for this process only: Start-Process -Wait would also wait for the launcher the installer starts, which never exits.
function RunAndWait([string] $exe, [string[]] $arguments) {
    $p = Start-Process $exe -ArgumentList $arguments -PassThru
    $p.WaitForExit()
    $p.ExitCode
}
function WaitFor([scriptblock] $condition, [int] $seconds = 30) {
    $deadline = (Get-Date).AddSeconds($seconds)
    while ((Get-Date) -lt $deadline) { if (& $condition) { return $true }; Start-Sleep -Milliseconds 500 }
    return [bool](& $condition)
}

Write-Host "== install $Setup"
$log = Join-Path ([IO.Path]::GetTempPath()) 'footnote-setup.log'
$code = RunAndWait $Setup @('/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART', '/TASKS="startup,desktopicon,addtopath"', "/LOG=`"$log`"")
Check "installer exit code 0 (got $code)" ($code -eq 0)
foreach ($f in 'footnote.exe', 'footnote-launcher.exe', 'unins000.exe') { Check "installed $f" (Test-Path (Join-Path $app $f)) }
foreach ($f in 'vcruntime140.dll', 'vcruntime140_1.dll', 'msvcp140.dll', 'msvcp140_1.dll', 'vcomp140.dll') {
    Check "runtime $f beside the engine" (Test-Path (Join-Path $app $f))
}
Check 'Start menu shortcut' (Test-Path $startMenu)
Check 'desktop shortcut (task selected)' (Test-Path $desktop)
Check 'starts with Windows in the tray (Run key with --tray)' ((RunValue) -like '*footnote-launcher.exe*--tray*')
Check 'on PATH exactly once' ((PathEntries) -eq 1)
$version = & (Join-Path $app 'footnote.exe') --version 2>&1
Check "engine runs: $version" ($LASTEXITCODE -eq 0 -and "$version" -like 'footnote *')
Check 'launcher running in the tray after install' (WaitFor { (Launchers).Count -ge 1 })
Check 'launcher opens no window at startup' (@(Launchers | Where-Object { $_.MainWindowTitle -eq 'Footnote' }).Count -eq 0)

Write-Host '== open the Start menu shortcut while it runs'
$before = @(Launchers).Count
Start-Process $startMenu
$shown = WaitFor { @(Launchers | Where-Object { $_.MainWindowTitle -eq 'Footnote' }).Count -ge 1 } 20
if ($env:GITHUB_ACTIONS -eq 'true' -and -not $shown) {
    # Hosted runners have no visible desktop, so no window title shows up there; checked on a real desktop instead.
    Write-Host 'note  shortcut window not visible on this runner (no desktop); the single-instance check below still applies'
} else {
    Check 'shortcut shows the Footnote window' $shown
}
Check "still one launcher (was $before)" (WaitFor { (Launchers).Count -eq $before } 10)

if (-not $KeepInstalled) {
    Write-Host '== uninstall'
    # The uninstaller relaunches itself from a temporary copy, so wait for the files to go rather than for the first process.
    RunAndWait (Join-Path $app 'unins000.exe') @('/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART') | Out-Null
    Check 'program files removed' (WaitFor { -not (Test-Path (Join-Path $app 'footnote.exe')) -and -not (Test-Path (Join-Path $app 'unins000.exe')) } 60)
    # The PATH entry goes last (post-uninstall step), after the files: wait for the temporary uninstaller (_iu*.tmp) to exit.
    WaitFor { -not (Get-Process | Where-Object { $_.Path -like '*\_iu*.tmp' }) } 60 | Out-Null
    Check 'Start menu shortcut removed' (-not (Test-Path $startMenu))
    Check 'desktop shortcut removed' (-not (Test-Path $desktop))
    Check 'startup entry removed' (-not (RunValue))
    Check 'PATH entry removed' (WaitFor { (PathEntries) -eq 0 } 30)
    Check 'launcher stopped' (WaitFor { (Launchers).Count -eq 0 } 20)
}

if ($failures.Count) {
    Write-Host "`n$($failures.Count) check(s) failed:"; $failures | ForEach-Object { Write-Host "  - $_" }
    if (Test-Path $log) { Write-Host "`n-- installer log (tail)"; Get-Content $log -Tail 40 }
    exit 1
}
Write-Host "`nall checks passed"
