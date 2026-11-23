#requires -Version 5.1
<#
.SYNOPSIS
    Point Antigravity on Windows at the Footnote installed natively in WSL 2: MCP server and memory hooks.

.DESCRIPTION
    For an agent that runs on the Windows side while Footnote runs in WSL 2 (scripts/wsl-install.sh). Writes the
    "footnote-memory" entries of Antigravity's ~/.gemini/config/mcp_config.json and hooks.json:

        MCP server:   <absolute path of wsl.exe> -d <Distro> -- <WSL home>/.local/bin/footnote-wsl-env --db <WSL db> mcp
        memory hooks: <absolute path of wsl.exe> -d <Distro> -- <WSL home>/.local/bin/footnote-wsl-env hook

    Claude Code and Codex are meant to run inside WSL, where scripts/wsl-agents.sh registers them with
    `footnote install`. An existing "footnote-memory" entry is kept unless -Force; -Remove deletes only entries that
    start Footnote through wsl.exe. Each file is backed up once (<file>.footnote-backup) before its first change.

.EXAMPLE
    powershell -NoProfile -ExecutionPolicy Bypass -File scripts\wsl-agents.ps1 -DryRun

.EXAMPLE
    powershell -NoProfile -ExecutionPolicy Bypass -File scripts\wsl-agents.ps1 -Distro Ubuntu
#>
[CmdletBinding()]
param(
    [string]$Distro = $(if ($env:FOOTNOTE_WSL_DISTRO) { $env:FOOTNOTE_WSL_DISTRO } else { 'Ubuntu' }),
    # The WSL user's home folder, e.g. /home/<user>. Asked from the distribution when left out.
    [string]$WslHome = '',
    [string]$HomeDir = $(if ($env:USERPROFILE) { $env:USERPROFILE } else { $HOME }),
    [switch]$DryRun,
    [switch]$Force,
    [switch]$Remove
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$Name = 'footnote-memory'
if ($Distro -notmatch '^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$') { throw "invalid -Distro '$Distro'" }
if ($Force -and $Remove) { throw '-Force and -Remove cannot be combined' }
if (-not (Test-Path -LiteralPath $HomeDir -PathType Container)) { throw "home folder not found: $HomeDir" }

$wslCmd = Get-Command wsl.exe -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1
if (-not $wslCmd -and -not $Remove) { throw 'wsl.exe is not on PATH: install WSL 2 first' }
$wsl = if ($wslCmd) { $wslCmd.Source -replace '\\', '/' } else { 'wsl.exe' }

if (-not $Remove) {
    if (-not $WslHome) {
        $WslHome = (& $wslCmd.Source -d $Distro -- sh -c 'printf %s "$HOME"' 2>$null | Out-String).Trim()
        if ($LASTEXITCODE -ne 0 -or -not $WslHome) { throw "could not read the home folder of WSL distribution '$Distro'" }
    }
    if ($WslHome -notmatch '^/[A-Za-z0-9_./-]+$') { throw "invalid -WslHome '$WslHome'" }
}
$WslWrapper = "$WslHome/.local/bin/footnote-wsl-env"
$Database = "$WslHome/.local/state/footnote/memory.db"

$mcpArgs = @('-d', $Distro, '--', $WslWrapper, '--db', $Database, 'mcp')
$hookExe = if ($wsl.Contains(' ')) { "`"$wsl`"" } else { $wsl }
$hookCommand = "$hookExe -d $Distro -- $WslWrapper hook"
$utf8 = New-Object System.Text.UTF8Encoding $false
$results = New-Object System.Collections.Generic.List[object]

function Add-Result([string]$Agent, [string]$Target, [string]$Status) {
    $s = if ($DryRun -and $Status -match '^(registered|replaced|removed)') { "$Status (dry run)" } else { $Status }
    $results.Add([pscustomobject]@{ Agent = $Agent; Target = $Target; Status = $s })
}

function Set-JsonFile([string]$Path, [object]$Root) {
    if ($DryRun) { return }
    $dir = Split-Path -Parent $Path
    if ($dir -and -not (Test-Path -LiteralPath $dir)) { New-Item -ItemType Directory -Path $dir -Force | Out-Null }
    if (Test-Path -LiteralPath $Path -PathType Leaf) {
        $backup = "$Path.footnote-backup"
        if (-not (Test-Path -LiteralPath $backup)) { Copy-Item -LiteralPath $Path -Destination $backup }
    }
    [IO.File]::WriteAllText($Path, ((ConvertTo-Json -InputObject $Root -Depth 100) + "`n"), $utf8)
}

function Read-JsonOrEmpty([string]$Path) {
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) { return (New-Object PSObject) }
    $raw = [IO.File]::ReadAllText($Path)
    if ([string]::IsNullOrWhiteSpace($raw)) { return (New-Object PSObject) }
    return (ConvertFrom-Json -InputObject $raw)
}

# True when a command line starts Footnote through wsl.exe (what this script writes), so -Remove leaves other entries alone.
function Test-WslCommand([string]$Command) {
    return ($Command -match '(^|[\\/"])wsl(\.exe)?"?(\s|$)') -and ($Command -match 'footnote')
}

function Update-McpJson([string]$Agent, [string]$Path) {
    $root = Read-JsonOrEmpty $Path
    if (-not $root.PSObject.Properties['mcpServers']) {
        $root | Add-Member -NotePropertyName 'mcpServers' -NotePropertyValue (New-Object PSObject)
    }
    $servers = $root.mcpServers
    $current = if ($servers.PSObject.Properties[$Name]) { $servers.$Name } else { $null }
    if ($Remove) {
        if ($null -eq $current) { Add-Result $Agent $Path 'not present'; return }
        $line = "$($current.command) $(@($current.args) -join ' ')"
        if (-not (Test-WslCommand $line)) { Add-Result $Agent $Path 'left alone (not a WSL entry)'; return }
        $servers.PSObject.Properties.Remove($Name)
        Set-JsonFile $Path $root
        Add-Result $Agent $Path 'removed'
        return
    }
    if ($null -ne $current -and -not $Force) {
        Add-Result $Agent $Path 'kept existing entry (use -Force to replace)'
        return
    }
    $entry = [pscustomobject]@{ command = $wsl; args = $mcpArgs }
    if ($null -ne $current) { $servers.$Name = $entry } else { $servers | Add-Member -NotePropertyName $Name -NotePropertyValue $entry }
    Set-JsonFile $Path $root
    Add-Result $Agent $Path ($(if ($null -ne $current) { 'replaced' } else { 'registered' }))
}

# Antigravity's named entry in hooks.json, in the form `footnote install` and scripts/docker-agents.ps1 write.
function Update-AgyHooks([string]$Path) {
    $agent = 'Antigravity (hooks)'
    $root = Read-JsonOrEmpty $Path
    $current = if ($root.PSObject.Properties[$Name]) { $root.$Name } else { $null }
    if ($Remove) {
        if ($null -eq $current) { Add-Result $agent $Path 'not present'; return }
        $commands = @($current.PSObject.Properties | ForEach-Object { @($_.Value) } | ForEach-Object { "$($_.command)" })
        if (-not $commands -or ($commands | Where-Object { -not (Test-WslCommand $_) })) {
            Add-Result $agent $Path 'left alone (not a WSL entry)'
            return
        }
        $root.PSObject.Properties.Remove($Name)
        Set-JsonFile $Path $root
        Add-Result $agent $Path 'removed'
        return
    }
    if ($null -ne $current -and -not $Force) {
        Add-Result $agent $Path 'kept existing entry (use -Force to replace)'
        return
    }
    $handler = { param($t) , @([pscustomobject][ordered]@{ type = 'command'; command = $hookCommand; timeout = $t }) }
    $entry = [pscustomobject][ordered]@{
        SessionStart = (& $handler 15); PreInvocation = (& $handler 10); Stop = (& $handler 5)
    }
    if ($null -ne $current) { $root.$Name = $entry } else { $root | Add-Member -NotePropertyName $Name -NotePropertyValue $entry }
    Set-JsonFile $Path $root
    Add-Result $agent $Path ($(if ($null -ne $current) { 'replaced' } else { 'registered' }))
}

$agyConfig = Join-Path $HomeDir '.gemini\config'
if (Test-Path -LiteralPath $agyConfig -PathType Container) {
    Update-McpJson 'Antigravity (MCP)' (Join-Path $agyConfig 'mcp_config.json')
    Update-AgyHooks (Join-Path $agyConfig 'hooks.json')
} else {
    Add-Result 'Antigravity' $agyConfig 'not found'
}

$results | Format-Table -AutoSize
