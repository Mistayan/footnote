#!/usr/bin/env bash
# Import and synchronize Windows (/mnt/c/...) codebases into WSL 2 native ext4 (~/workspaces/<repo>)
# so git status, footnote grep, code-index and the memory hooks read a Linux disk instead of the Windows one (WSL.md).
#
# Usage:
#   footnote-wsl-codebase import <windows-or-mnt-path> [--name <repo>] [--with-untracked] [--no-index]
#   footnote-wsl-codebase import-all <parent-dir> [--no-index]
#   footnote-wsl-codebase sync [<repo>|--all] [--no-index]
#   footnote-wsl-codebase list
set -euo pipefail

BIN_DIR="$HOME/.local/bin"
export PATH="$BIN_DIR:$HOME/.cargo/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"

STATE_DIR="${FOOTNOTE_STATE_DIR:-$HOME/.local/state/footnote}"
WORKSPACES_DIR="${FOOTNOTE_WSL_WORKSPACES:-$HOME/workspaces}"
PATH_MAP_ENV="$STATE_DIR/wsl-path-map.env"
MANIFEST="$STATE_DIR/wsl-codebases.tsv"
FOOTNOTE_BIN="$BIN_DIR/footnote-wsl-env"
if [ ! -x "$FOOTNOTE_BIN" ]; then
    FOOTNOTE_BIN="$BIN_DIR/footnote"
fi

mkdir -p "$STATE_DIR" "$WORKSPACES_DIR"
chmod 700 "$STATE_DIR"
touch "$MANIFEST"

# Convert a Windows path (C:\Users\dev\Desktop\foo or C:/Users/...) to a WSL /mnt/<drive>/... path.
to_wsl_path() {
    local raw="$1"
    if [[ "$raw" =~ ^([A-Za-z]):[\\/](.*)$ ]]; then
        local drive="${BASH_REMATCH[1],,}"
        local rest="${BASH_REMATCH[2]//\\//}"
        printf '/mnt/%s/%s\n' "$drive" "${rest%/}"
    elif command -v wslpath >/dev/null 2>&1 && [[ "$raw" == *\\* ]]; then
        wslpath -u "$raw"
    else
        printf '%s\n' "${raw%/}"
    fi
}

# Convert a WSL /mnt/<drive>/... path to a Windows C:\... path (empty when not under /mnt/<drive>/).
to_win_path() {
    local wsl_p="$1"
    if [[ "$wsl_p" =~ ^/mnt/([a-z])/(.*)$ ]]; then
        local drive="${BASH_REMATCH[1]^^}"
        local rest="${BASH_REMATCH[2]//\//\\}"
        printf '%s:\\%s\n' "$drive" "$rest"
    else
        printf '\n'
    fi
}

rebuild_path_map() {
    local entries=()
    while IFS=$'\t' read -r name src_wsl dst_ext4 win_path; do
        [ -z "$name" ] && continue
        [ -n "$src_wsl" ] && entries+=("${src_wsl}=${dst_ext4}")
        [ -n "$win_path" ] && entries+=("${win_path}=${dst_ext4}")
    done < "$MANIFEST"

    local joined=""
    local item
    for item in "${entries[@]}"; do
        if [ -z "$joined" ]; then
            joined="$item"
        else
            joined="${joined};${item}"
        fi
    done

    cat > "$PATH_MAP_ENV" << EOF
# Automatically managed by footnote-wsl-codebase.
# Maps Windows (C:\...) and DrvFs (/mnt/c/...) workspace paths to native ext4 clones ($WORKSPACES_DIR/<repo>).
FOOTNOTE_PATH_MAP='$joined'
EOF
    chmod 600 "$PATH_MAP_ENV"
}

record_manifest() {
    local name="$1"
    local src_wsl="$2"
    local dst_ext4="$3"
    local win_path="$4"
    local tmp="$MANIFEST.tmp"
    grep -v "^${name}	" "$MANIFEST" > "$tmp" 2>/dev/null || true
    printf '%s\t%s\t%s\t%s\n' "$name" "$src_wsl" "$dst_ext4" "$win_path" >> "$tmp"
    mv -f "$tmp" "$MANIFEST"
    rebuild_path_map
}

cmd_import() {
    local raw_src=""
    local custom_name=""
    local with_untracked=0
    local no_index=0

    while [ $# -gt 0 ]; do
        case "$1" in
            --name) custom_name="$2"; shift 2 ;;
            --with-untracked) with_untracked=1; shift ;;
            --no-index) no_index=1; shift ;;
            -*)
                echo "footnote-wsl-codebase import: unknown flag: $1" >&2
                exit 2
                ;;
            *)
                raw_src="$1"; shift ;;
        esac
    done

    if [ -z "$raw_src" ]; then
        echo "Usage: footnote-wsl-codebase import <path> [--name <repo>] [--with-untracked] [--no-index]" >&2
        exit 2
    fi

    local src_wsl
    src_wsl="$(to_wsl_path "$raw_src")"
    if [ ! -d "$src_wsl" ]; then
        echo "footnote-wsl-codebase: source folder not found: $raw_src (resolved to $src_wsl)" >&2
        exit 1
    fi
    src_wsl="$(cd "$src_wsl" && pwd)"

    local name="$custom_name"
    if [ -z "$name" ]; then
        name="$(basename "$src_wsl" | tr '[:upper:] ' '[:lower:]-')"
    fi
    local dst_ext4="$WORKSPACES_DIR/$name"
    local win_path
    win_path="$(to_win_path "$src_wsl")"

    echo "Importing '$name' from $src_wsl -> $dst_ext4 (ext4)..."
    if [ -d "$src_wsl/.git" ] || [ -f "$src_wsl/.git" ]; then
        local orig_url=""
        orig_url="$(git -c core.autocrlf=true -C "$src_wsl" remote get-url origin 2>/dev/null || true)"
        local branch=""
        branch="$(git -c core.autocrlf=true -C "$src_wsl" rev-parse --abbrev-ref HEAD 2>/dev/null || true)"

        if [ -d "$dst_ext4/.git" ]; then
            echo "  Target $dst_ext4 already exists; fetching from windows source..."
            git -C "$dst_ext4" remote set-url windows "$src_wsl" 2>/dev/null || \
                git -C "$dst_ext4" remote add windows "$src_wsl"
            git -C "$dst_ext4" fetch --quiet windows
        else
            if [ -e "$dst_ext4" ] && [ -n "$(ls -A "$dst_ext4" 2>/dev/null)" ]; then
                echo "footnote-wsl-codebase: $dst_ext4 exists and is not a git clone; move it away or pass --name" >&2
                exit 1
            fi
            git clone --quiet "$src_wsl" "$dst_ext4"
            git -C "$dst_ext4" remote rename origin windows 2>/dev/null || true
            if [ -n "$orig_url" ]; then
                git -C "$dst_ext4" remote add origin "$orig_url"
            else
                git -C "$dst_ext4" remote add origin "$src_wsl"
            fi
            if [ -n "$branch" ] && [ "$branch" != "HEAD" ]; then
                git -C "$dst_ext4" checkout --quiet "$branch" 2>/dev/null || true
            fi
        fi

        if [ "$with_untracked" -eq 1 ] && command -v rsync >/dev/null 2>&1; then
            echo "  Syncing working-tree edits (excluding build artifacts and .git)..."
            rsync -a \
                --exclude='.git' \
                --exclude='.scratch' \
                --exclude='target' \
                --exclude='target-*' \
                --exclude='node_modules' \
                --exclude='dist' \
                --exclude='build' \
                --exclude='.venv' \
                --exclude='venv' \
                --exclude='__pycache__' \
                "$src_wsl/" "$dst_ext4/"
        fi
    else
        mkdir -p "$dst_ext4"
        if command -v rsync >/dev/null 2>&1; then
            rsync -a --delete \
                --exclude='.git' \
                --exclude='.scratch' \
                --exclude='target' \
                --exclude='target-*' \
                --exclude='node_modules' \
                --exclude='dist' \
                --exclude='build' \
                --exclude='.venv' \
                --exclude='venv' \
                --exclude='__pycache__' \
                "$src_wsl/" "$dst_ext4/"
        else
            cp -a "$src_wsl/." "$dst_ext4/"
        fi
    fi

    # A quick-access symlink $HOME/<name>, when that name is free
    if [ ! -e "$HOME/$name" ]; then
        ln -s "$dst_ext4" "$HOME/$name"
    fi

    record_manifest "$name" "$src_wsl" "$dst_ext4" "$win_path"

    if [ -x "$FOOTNOTE_BIN" ]; then
        "$FOOTNOTE_BIN" projects add "$dst_ext4" >/dev/null 2>&1 || true
        if [ "$no_index" -eq 0 ]; then
            echo "  Building Footnote Code graph on ext4 ($dst_ext4)..."
            "$FOOTNOTE_BIN" code-index "$dst_ext4"
        fi
    fi
    echo "  Imported '$name' -> $dst_ext4"
}

cmd_import_all() {
    local parent_raw="${1:-}"
    shift || true
    if [ -z "$parent_raw" ]; then
        echo "Usage: footnote-wsl-codebase import-all <parent-dir> [--no-index]" >&2
        exit 2
    fi
    local parent_wsl
    parent_wsl="$(to_wsl_path "$parent_raw")"
    if [ ! -d "$parent_wsl" ]; then
        echo "footnote-wsl-codebase: folder not found: $parent_raw" >&2
        exit 1
    fi
    local count=0
    for dir in "$parent_wsl"/*; do
        [ -d "$dir" ] || continue
        if [ -d "$dir/.git" ]; then
            cmd_import "$dir" "$@"
            count=$((count + 1))
        fi
    done
    echo "Imported $count Git repositories from $parent_wsl into $WORKSPACES_DIR."
}

cmd_sync() {
    local target="${1:---all}"
    local no_index=0
    for arg in "$@"; do
        [ "$arg" = "--no-index" ] && no_index=1
    done

    while IFS=$'\t' read -r name src_wsl dst_ext4 win_path; do
        [ -z "$name" ] && continue
        if [ "$target" != "--all" ] && [ "$target" != "$name" ]; then
            continue
        fi
        if [ ! -d "$dst_ext4" ]; then
            cmd_import "$src_wsl" --name "$name" $([ "$no_index" -eq 1 ] && echo "--no-index")
            continue
        fi
        echo "Syncing '$name' ($src_wsl -> $dst_ext4)..."
        if [ -d "$dst_ext4/.git" ] && git -C "$dst_ext4" remote get-url windows >/dev/null 2>&1; then
            git -C "$dst_ext4" fetch --quiet windows
            if [ -z "$(git -C "$dst_ext4" status --porcelain)" ]; then
                local br
                br="$(git -C "$dst_ext4" rev-parse --abbrev-ref HEAD)"
                git -C "$dst_ext4" merge --ff-only "windows/$br" >/dev/null 2>&1 || true
            fi
        elif command -v rsync >/dev/null 2>&1 && [ -d "$src_wsl" ]; then
            rsync -a \
                --exclude='.git' \
                --exclude='.scratch' \
                --exclude='target' \
                --exclude='target-*' \
                --exclude='node_modules' \
                "$src_wsl/" "$dst_ext4/"
        fi
        if [ "$no_index" -eq 0 ] && [ -x "$FOOTNOTE_BIN" ]; then
            "$FOOTNOTE_BIN" code-index "$dst_ext4" >/dev/null
        fi
    done < "$MANIFEST"
}

cmd_list() {
    printf "%-20s %-38s %-45s %s\n" "PROJECT" "WSL EXT4 PATH" "WINDOWS SOURCE" "BRANCH"
    printf "%-20s %-38s %-45s %s\n" "-------" "-------------" "--------------" "------"
    while IFS=$'\t' read -r name src_wsl dst_ext4 win_path; do
        [ -z "$name" ] && continue
        local br="-"
        if [ -d "$dst_ext4/.git" ]; then
            br="$(git -C "$dst_ext4" rev-parse --abbrev-ref HEAD 2>/dev/null || echo '?')"
        fi
        printf "%-20s %-38s %-45s %s\n" "$name" "$dst_ext4" "${win_path:-$src_wsl}" "$br"
    done < "$MANIFEST"
}

subcmd="${1:-list}"
shift || true
case "$subcmd" in
    import)     cmd_import "$@" ;;
    import-all) cmd_import_all "$@" ;;
    sync)       cmd_sync "$@" ;;
    list|status) cmd_list ;;
    -h|--help)
        sed -n '2,10p' "${BASH_SOURCE[0]}"
        ;;
    *)
        echo "footnote-wsl-codebase: unknown command '$subcmd' (expected: import, import-all, sync, list)" >&2
        exit 2
        ;;
esac
