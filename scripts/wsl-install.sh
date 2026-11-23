#!/usr/bin/env bash
# Footnote native WSL 2 installer: builds on ext4, sets up a clean Linux PATH wrapper,
# migrates or installs embedding models, starts the resident daemon, and wires agents.
#
# Usage:
#   bash scripts/wsl-install.sh [options]
#
# Options:
#   --skip-build              Use an already-built binary in $CARGO_TARGET_DIR or ~/.local/bin/footnote
#   --target-dir <dir>        Cargo target directory on ext4 (default: ~/.cache/footnote-target)
#   --state-dir <dir>         Footnote state directory on ext4 (default: ~/.local/state/footnote)
#   --from-db <file>          Seed memory.db from an existing backup file if state has no memory.db
#   --from-models <dir>       Copy pre-downloaded ONNX models from <dir> into <state-dir>/models
#   --install-models          Download default models (bekko-a8m, gte-small) via `footnote models install`
#   --sync-win-configs        Copy agent settings (.claude, .codex, .gemini/config) from the Windows home where WSL has none; never credentials
#   --import-repo <path>      Import a codebase from Windows (/mnt/c/...) to ~/workspaces/<repo> on ext4
#   --dry-run                 Preview agent registrations without modifying agent config files
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

TARGET_DIR="${FOOTNOTE_WSL_TARGET_DIR:-$HOME/.cache/footnote-target}"
STATE_DIR="${FOOTNOTE_STATE_DIR:-$HOME/.local/state/footnote}"
BIN_DIR="$HOME/.local/bin"
SKIP_BUILD=0
FROM_DB=""
FROM_MODELS=""
INSTALL_MODELS=0
SYNC_WIN_CONFIGS=0
DRY_RUN=0
IMPORT_REPOS=()

while [ $# -gt 0 ]; do
    case "$1" in
        --skip-build) SKIP_BUILD=1; shift ;;
        --target-dir) TARGET_DIR="$2"; shift 2 ;;
        --state-dir) STATE_DIR="$2"; shift 2 ;;
        --from-db) FROM_DB="$2"; shift 2 ;;
        --from-models) FROM_MODELS="$2"; shift 2 ;;
        --install-models) INSTALL_MODELS=1; shift ;;
        --sync-win-configs) SYNC_WIN_CONFIGS=1; shift ;;
        --import-repo) IMPORT_REPOS+=("$2"); shift 2 ;;
        --dry-run) DRY_RUN=1; shift ;;
        -h|--help)
            sed -n '2,18p' "${BASH_SOURCE[0]}"
            exit 0
            ;;
        *)
            echo "wsl-install.sh: unknown option: $1" >&2
            exit 2
            ;;
    esac
done

export PATH="$BIN_DIR:$HOME/.cargo/bin:/usr/local/bin:/usr/bin:/bin"

mkdir -p "$BIN_DIR" "$STATE_DIR"
chmod 700 "$STATE_DIR"

# 1. Build on native ext4 so Cargo never writes intermediate artifacts over /mnt/c (9P).
if [ "$SKIP_BUILD" -eq 0 ]; then
    if ! command -v cargo >/dev/null 2>&1; then
        echo "wsl-install.sh: cargo not found in WSL. Install Rust with: curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh" >&2
        exit 1
    fi
    mkdir -p "$TARGET_DIR"
    echo "[1/5] Building footnote release binary on ext4 (CARGO_TARGET_DIR=$TARGET_DIR)..."
    (
        cd "$REPO_ROOT"
        CARGO_TARGET_DIR="$TARGET_DIR" cargo build --locked --release --bin footnote
    )
    cp "$TARGET_DIR/release/footnote" "$BIN_DIR/footnote.new"
    chmod 755 "$BIN_DIR/footnote.new"
    mv -f "$BIN_DIR/footnote.new" "$BIN_DIR/footnote"
else
    if [ -x "$TARGET_DIR/release/footnote" ] && [ ! -x "$BIN_DIR/footnote" ]; then
        cp "$TARGET_DIR/release/footnote" "$BIN_DIR/footnote"
        chmod 755 "$BIN_DIR/footnote"
    fi
    if [ ! -x "$BIN_DIR/footnote" ]; then
        echo "wsl-install.sh: --skip-build specified, but $BIN_DIR/footnote does not exist" >&2
        exit 1
    fi
    echo "[1/5] Using existing binary: $BIN_DIR/footnote ($("$BIN_DIR/footnote" --version))"
fi

# 2. Install helper scripts (`footnote-wsl-env` and `footnote-wsl-codebase`).
echo "[2/5] Installing WSL wrapper and codebase importer to $BIN_DIR..."
cp "$SCRIPT_DIR/wsl-codebase.sh" "$BIN_DIR/footnote-wsl-codebase"
chmod 755 "$BIN_DIR/footnote-wsl-codebase"

PATH_MAP_ENV="$STATE_DIR/wsl-path-map.env"
if [ ! -f "$PATH_MAP_ENV" ]; then
    cat > "$PATH_MAP_ENV" << 'EOF'
# Automatically managed by footnote-wsl-codebase.
# Maps Windows (C:\...) and DrvFs (/mnt/c/...) workspace paths to native ext4 clones (~/workspaces/<repo>).
FOOTNOTE_PATH_MAP=
EOF
    chmod 600 "$PATH_MAP_ENV"
fi

cat > "$BIN_DIR/footnote-wsl-env" << EOF
#!/usr/bin/env bash
# Zero-9P environment wrapper for Footnote in WSL 2:
# - Strips Windows /mnt/c entries from PATH so process probes stay on ext4.
# - Loads FOOTNOTE_PATH_MAP from $PATH_MAP_ENV when present.
export PATH="$BIN_DIR:$HOME/.cargo/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
export FOOTNOTE_STATE_DIR="${STATE_DIR}"
if [ -f "${PATH_MAP_ENV}" ]; then
    # shellcheck disable=SC1090
    . "${PATH_MAP_ENV}"
    export FOOTNOTE_PATH_MAP
fi
exec "$BIN_DIR/footnote" "\$@"
EOF
chmod 755 "$BIN_DIR/footnote-wsl-env"

# 3. Seed or configure state (memory.db and embedding models).
echo "[3/5] Configuring Footnote state in $STATE_DIR..."
export FOOTNOTE_STATE_DIR="$STATE_DIR"

if [ -n "$FROM_DB" ] && [ -f "$FROM_DB" ] && [ ! -f "$STATE_DIR/memory.db" ]; then
    cp "$FROM_DB" "$STATE_DIR/memory.db"
    chmod 600 "$STATE_DIR/memory.db"
    echo "      Imported memory.db from $FROM_DB"
fi

if [ -n "$FROM_MODELS" ] && [ -d "$FROM_MODELS" ]; then
    mkdir -p "$STATE_DIR/models"
    cp -rn "$FROM_MODELS/"* "$STATE_DIR/models/" 2>/dev/null || cp -r "$FROM_MODELS/"* "$STATE_DIR/models/"
    echo "      Copied models from $FROM_MODELS into $STATE_DIR/models"
fi

if [ "$INSTALL_MODELS" -eq 1 ]; then
    "$BIN_DIR/footnote-wsl-env" models install bekko-a8m gte-small
    "$BIN_DIR/footnote-wsl-env" models use bekko-a8m gte-small
elif [ -d "$STATE_DIR/models/bekko-a8m" ] && [ -d "$STATE_DIR/models/gte-small" ]; then
    "$BIN_DIR/footnote-wsl-env" models use bekko-a8m gte-small >/dev/null 2>&1 || \
    cat > "$STATE_DIR/memory.json" << EOF
{
  "models": [
    "$STATE_DIR/models/bekko-a8m",
    "$STATE_DIR/models/gte-small"
  ]
}
EOF
fi

# 4. Configure the resident Footnote memory daemon in WSL.
# Note: `footnote hook` automatically spawns the resident daemon on demand with detached stdio (`resident: true` by default).
# We only enable a systemd user unit when `systemctl --user status` is genuinely active in this WSL instance.
echo "[4/5] Configuring resident Footnote memory daemon in WSL..."
if command -v systemctl >/dev/null 2>&1 && systemctl --user status >/dev/null 2>&1; then
    SYSTEMD_DIR="$HOME/.config/systemd/user"
    mkdir -p "$SYSTEMD_DIR"
    cat > "$SYSTEMD_DIR/footnote-memory.service" << EOF
[Unit]
Description=Footnote Resident Memory & MCP Daemon (WSL 2 ext4)
After=network.target

[Service]
Type=simple
Environment="PATH=$BIN_DIR:$HOME/.cargo/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
Environment="FOOTNOTE_STATE_DIR=$STATE_DIR"
EnvironmentFile=-$PATH_MAP_ENV
ExecStart=$BIN_DIR/footnote --db $STATE_DIR/memory.db serve --mcp --daemon
Restart=on-failure
RestartSec=2

[Install]
WantedBy=default.target
EOF
    systemctl --user daemon-reload
    systemctl --user enable --now footnote-memory.service
    echo "      Enabled and started systemd user service: footnote-memory.service"
else
    echo "      On-demand resident daemon enabled via footnote hook (resident: true)"
fi

# Ensure ~/.profile puts ~/.local/bin on PATH and exports FOOTNOTE_STATE_DIR (never spawn background processes in .profile).
PROFILE_MARKER="# >>> footnote-wsl >>>"
if [ -f "$HOME/.profile" ] && ! grep -q "$PROFILE_MARKER" "$HOME/.profile"; then
    cat >> "$HOME/.profile" << EOF

$PROFILE_MARKER
export PATH="\$HOME/.local/bin:\$PATH"
export FOOTNOTE_STATE_DIR="$STATE_DIR"
# <<< footnote-wsl <<<
EOF
fi

# 5. Import requested codebases to ext4 and register agents.
for repo_path in "${IMPORT_REPOS[@]}"; do
    "$BIN_DIR/footnote-wsl-codebase" import "$repo_path"
done

echo "[5/5] Linking and registering coding agents in WSL..."
AGENT_ARGS=()
if [ "$SYNC_WIN_CONFIGS" -eq 1 ]; then
    AGENT_ARGS+=("--sync-win-configs")
fi
if [ "$DRY_RUN" -eq 1 ]; then
    AGENT_ARGS+=("--dry-run")
fi
bash "$SCRIPT_DIR/wsl-agents.sh" "${AGENT_ARGS[@]}"

echo ""
echo "Footnote WSL 2 installation complete."
"$BIN_DIR/footnote-wsl-env" status
