#!/usr/bin/env bash
# Link and register coding agents (Claude Code, Codex, Antigravity, Cygwin / Git Bash)
# for a 100% WSL 2 Footnote workflow.
#
# Usage:
#   bash scripts/wsl-agents.sh [--sync-win-configs] [--win-home /mnt/c/Users/<user>] [--dry-run] [--remove]
set -euo pipefail

BIN_DIR="$HOME/.local/bin"
export PATH="$BIN_DIR:$HOME/.cargo/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"

STATE_DIR="${FOOTNOTE_STATE_DIR:-$HOME/.local/state/footnote}"
SYNC_WIN_CONFIGS=0
WIN_HOME=""
DRY_RUN=0
REMOVE=0

while [ $# -gt 0 ]; do
    case "$1" in
        --sync-win-configs) SYNC_WIN_CONFIGS=1; shift ;;
        --win-home) WIN_HOME="$2"; shift 2 ;;
        --dry-run) DRY_RUN=1; shift ;;
        --remove) REMOVE=1; shift ;;
        -h|--help)
            sed -n '2,7p' "${BASH_SOURCE[0]}"
            exit 0
            ;;
        *)
            echo "wsl-agents.sh: unknown option: $1" >&2
            exit 2
            ;;
    esac
done

FOOTNOTE_WRAPPER="$BIN_DIR/footnote-wsl-env"
if [ ! -x "$FOOTNOTE_WRAPPER" ]; then
    FOOTNOTE_WRAPPER="$BIN_DIR/footnote"
fi
if [ ! -x "$FOOTNOTE_WRAPPER" ]; then
    echo "wsl-agents.sh: footnote binary not found in $BIN_DIR. Run scripts/wsl-install.sh first." >&2
    exit 1
fi

# Detect Windows user home under /mnt/c/Users/<user> if not explicitly passed
if [ -z "$WIN_HOME" ]; then
    if [ -d "/mnt/c/Users/$USER" ]; then
        WIN_HOME="/mnt/c/Users/$USER"
    else
        for candidate in /mnt/c/Users/*; do
            base="$(basename "$candidate")"
            case "$base" in
                Public|Default|"Default User"|"All Users"|desktop.ini) continue ;;
            esac
            if [ -d "$candidate/.claude" ] || [ -d "$candidate/.codex" ] || [ -d "$candidate/.gemini" ]; then
                WIN_HOME="$candidate"
                break
            fi
        done
    fi
fi

# 1. Optionally seed WSL agent settings (settings, hooks, MCP; never transcripts) from the Windows home, only where WSL has none.
#    Credentials are never copied: sign in to each agent inside WSL.
sync_file_if_missing() {
    local src="$1"
    local dst="$2"
    if [ -f "$src" ] && [ ! -e "$dst" ]; then
        if [ "$DRY_RUN" -eq 1 ]; then
            echo "  [dry-run] would copy $src -> $dst"
        else
            mkdir -p "$(dirname "$dst")"
            cp "$src" "$dst"
            echo "  Copied $src -> $dst"
        fi
    fi
}

if [ "$DRY_RUN" -eq 0 ]; then
    mkdir -p "$HOME/.claude" "$HOME/.codex" "$HOME/.gemini/config"
fi

if [ "$SYNC_WIN_CONFIGS" -eq 1 ] && [ -n "$WIN_HOME" ] && [ -d "$WIN_HOME" ]; then
    echo "Syncing agent configuration files from $WIN_HOME into WSL $HOME..."
    for rel in \
        ".claude/settings.json" \
        ".codex/config.toml" \
        ".codex/hooks.json" \
        ".gemini/config/mcp_config.json" \
        ".gemini/config/hooks.json"
    do
        sync_file_if_missing "$WIN_HOME/$rel" "$HOME/$rel"
    done
fi

# 2. Create CLI links in ~/.local/bin for claude, codex and agy when installed in NVM/NPM/Windows.
link_cli_if_missing() {
    local name="$1"
    shift
    if command -v "$name" >/dev/null 2>&1; then
        return 0
    fi
    for candidate in "$@"; do
        if [ -x "$candidate" ]; then
            if [ "$DRY_RUN" -eq 1 ]; then
                echo "  [dry-run] would link $BIN_DIR/$name -> $candidate"
            else
                ln -sf "$candidate" "$BIN_DIR/$name"
                echo "  Linked $BIN_DIR/$name -> $candidate"
            fi
            return 0
        fi
    done
}

if [ -n "$WIN_HOME" ] && [ "$REMOVE" -eq 0 ]; then
    link_cli_if_missing claude \
        "$HOME/.npm-global/bin/claude" \
        "$HOME/.local/share/pnpm/claude" \
        "$WIN_HOME/.local/bin/claude.exe" \
        "$WIN_HOME/AppData/Roaming/npm/claude"
    link_cli_if_missing codex \
        "$HOME/.npm-global/bin/codex" \
        "$WIN_HOME/AppData/Roaming/npm/codex"
    link_cli_if_missing agy \
        "$WIN_HOME/AppData/Local/Programs/Antigravity/bin/agy" \
        "$WIN_HOME/.gemini/antigravity-cli/agy"
fi

# 3. Create a Cygwin / Git Bash / MSYS2 bridge shim (`footnote` and `cyg` helper) so Cygwin or Git Bash terminals
#    transparently execute the native WSL ext4 Footnote binary and daemon.
CYG_SHIM="$STATE_DIR/footnote-cygwin-shim.sh"
if [ "$DRY_RUN" -eq 0 ] && [ "$REMOVE" -eq 0 ]; then
    mkdir -p "$STATE_DIR"
    cat > "$CYG_SHIM" << EOF
#!/usr/bin/env bash
# Cygwin / Git Bash / MSYS2 bridge to Footnote running natively in WSL 2 ($WSL_DISTRO_NAME).
exec wsl.exe -d "${WSL_DISTRO_NAME:-Ubuntu}" -- "$FOOTNOTE_WRAPPER" "\$@"
EOF
    chmod 755 "$CYG_SHIM"

    # Install into Cygwin or Windows ~/.local/bin if present on /mnt/c
    for cyg_bin in "/mnt/c/cygwin64/usr/local/bin" "/mnt/c/cygwin/usr/local/bin" "${WIN_HOME:+$WIN_HOME/.local/bin}"; do
        if [ -n "$cyg_bin" ] && [ -d "$cyg_bin" ]; then
            # Never replace a `footnote` that is not this shim (a native footnote.exe build, another tool).
            if [ -e "$cyg_bin/footnote" ] && ! grep -q 'bridge to Footnote running natively in WSL' "$cyg_bin/footnote" 2>/dev/null; then
                echo "  Left $cyg_bin/footnote alone: it is not this shim"
                continue
            fi
            cp "$CYG_SHIM" "$cyg_bin/footnote" && chmod 755 "$cyg_bin/footnote"
            echo "  Installed Cygwin/Git-Bash shim: $cyg_bin/footnote -> WSL $FOOTNOTE_WRAPPER"
        fi
    done
fi

# 4. Run native `footnote install --memory --lean` inside WSL so the WSL agents (Claude Code, Codex, Antigravity) use the
#    native WSL binary and resident daemon directly.
INSTALL_FLAGS=("--memory" "--lean")
if [ "$DRY_RUN" -eq 1 ]; then
    INSTALL_FLAGS+=("--dry-run")
fi

if [ "$REMOVE" -eq 1 ]; then
    echo "Removing Footnote Memory and Lean registrations in WSL..."
    "$FOOTNOTE_WRAPPER" uninstall "${INSTALL_FLAGS[@]}"
else
    echo "Registering Footnote Memory and Lean hooks + MCP server across WSL agents..."
    "$FOOTNOTE_WRAPPER" install "${INSTALL_FLAGS[@]}"
fi
