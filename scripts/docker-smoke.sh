#!/usr/bin/env bash
# End-to-end smoke verification for the official Footnote Docker image (#392).
# Runs completely isolated with a temporary named Docker volume and cleans up on exit.
# Linux, macOS, and Git Bash on Windows; python3 is optional.
set -euo pipefail

IMAGE="${1:-footnote:local}"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
STATE_DIR=/state
WORKSPACE_DIR=/workspace
WORKSPACES_DIR=/workspaces
DB_PATH="${STATE_DIR}/memory.db"
EXPECTED_UID=10001
HOST_PREFIX='C:\work\repos'
HOST_REPO="${HOST_PREFIX}\\footnote"
HOST_TRANSCRIPT='C:\Users\smoke\.claude\projects\footnote\smoke.jsonl'
SUFFIX="$$-$(date +%s)"
MARKER="docker-smoke-${SUFFIX}"
TODAY="$(date -u +%Y-%m-%d)"
STATE_VOL="footnote-smoke-state-${SUFFIX}"
DAEMON_NAME="footnote-smoke-daemon-${SUFFIX}"
SCRATCH="$(mktemp -d)"
INIT='{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"smoke","version":"1"}}}'
TOOLS_LIST='{"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}}'

# Git Bash: Docker needs Windows paths for bind mounts, and MSYS must not rewrite container paths (/var/lib/...).
host_path() { if command -v cygpath >/dev/null 2>&1; then cygpath -w "$1"; else printf '%s' "$1"; fi; }
if command -v cygpath >/dev/null 2>&1; then export MSYS_NO_PATHCONV=1 MSYS2_ARG_CONV_EXCL='*'; fi
REPO_MOUNT="$(host_path "${REPO_ROOT}")"
have_python() { python3 -c 'import json' >/dev/null 2>&1; }

cleanup() {
  docker rm -f "${DAEMON_NAME}" >/dev/null 2>&1 || true
  docker volume rm -f "${STATE_VOL}" >/dev/null 2>&1 || true
  rm -rf -- "${SCRATCH:?}"
}
trap cleanup EXIT

HARDENED_ARGS=(
  --network none
  --read-only
  --tmpfs /tmp:rw,noexec,nosuid,size=64m
  --cap-drop=ALL
  --security-opt=no-new-privileges:true
)

echo "[1/10] Verify non-root user (UID ${EXPECTED_UID}), git, scoped git trust, and system CA bundle"
uid="$(docker run --rm --entrypoint id "${IMAGE}" -u)"
[ "${uid}" = "${EXPECTED_UID}" ] || { echo "Expected UID ${EXPECTED_UID}, got ${uid}" >&2; exit 1; }
docker run --rm --entrypoint git "${IMAGE}" --version >/dev/null
docker run --rm --entrypoint test "${IMAGE}" -s /etc/ssl/certs/ca-certificates.crt
if docker run --rm --entrypoint sh "${IMAGE}" -c 'command -v curl >/dev/null 2>&1'; then
  echo "Unexpected curl found in minimal runtime image" >&2
  exit 1
fi
if docker run --rm --entrypoint git "${IMAGE}" config --system --get-all safe.directory | grep -qx '\*'; then
  echo "git trusts every directory (safe.directory=*): only the workspace mounts may be trusted" >&2
  exit 1
fi

echo "[2/10] Verify one-shot CLI under hardened flags (--network none --read-only)"
docker run --rm "${HARDENED_ARGS[@]}" "${IMAGE}" --version
docker run --rm "${HARDENED_ARGS[@]}" \
  -v "${STATE_VOL}:${STATE_DIR}" \
  "${IMAGE}" status >/dev/null

echo "[3/10] Verify read-only Markdown index/search, code-index (tree-sitter), and grep"
notes="${SCRATCH}/notes"
mkdir -p "${notes}"
printf 'walcheckpoint records transaction progress\n' >"${notes}/archive.md"
notes_mount="$(host_path "${notes}")"
docker run --rm "${HARDENED_ARGS[@]}" \
  -v "${STATE_VOL}:${STATE_DIR}" \
  -v "${notes_mount}:/notes:ro" \
  "${IMAGE}" --db "${STATE_DIR}/docs.db" index --root /notes --allow /notes >/dev/null
docker run --rm "${HARDENED_ARGS[@]}" \
  -v "${STATE_VOL}:${STATE_DIR}" \
  -v "${notes_mount}:/notes:ro" \
  "${IMAGE}" --db "${STATE_DIR}/docs.db" search walcheckpoint | grep -q 'archive.md' || {
  echo "Markdown index/search smoke check failed" >&2
  exit 1
}
docker run --rm "${HARDENED_ARGS[@]}" \
  -v "${STATE_VOL}:${STATE_DIR}" \
  -v "${REPO_MOUNT}:${WORKSPACE_DIR}:ro" \
  "${IMAGE}" code-index "${WORKSPACE_DIR}" >/dev/null
docker run --rm "${HARDENED_ARGS[@]}" \
  -v "${STATE_VOL}:${STATE_DIR}" \
  -v "${REPO_MOUNT}:${WORKSPACE_DIR}:ro" \
  "${IMAGE}" grep "map_host_path" "${WORKSPACE_DIR}" --glob "*.rs" >/dev/null

echo "[4/10] Verify MCP tools/list byte budget (<= 5,000 B, 8 tools) over serve --mcp"
mcp_out="$(printf '%s\n%s\n' "${INIT}" "${TOOLS_LIST}" \
  | docker run --rm -i "${HARDENED_ARGS[@]}" \
      -v "${STATE_VOL}:${STATE_DIR}" \
      "${IMAGE}" --db "${DB_PATH}" serve --mcp)"
replies="$(printf '%s\n' "${mcp_out}" | grep -c .)"
[ "${replies}" = 2 ] || { echo "expected 2 JSON-RPC replies, got ${replies}" >&2; exit 1; }
tools_reply="$(printf '%s\n' "${mcp_out}" | grep . | sed -n 2p)"
tools="$(printf '%s' "${tools_reply}" | { grep -o '"inputSchema"' || true; } | wc -l | tr -d ' ')"
# The reply is compact JSON: the result is the line minus the envelope's keys and the closing brace.
envelope='{"jsonrpc":"2.0","id":2,"result":'
size=$(($(printf '%s' "${tools_reply}" | LC_ALL=C wc -c | tr -d ' ') - ${#envelope} - 1))
[ "${tools}" = 8 ] || { echo "expected 8 tools, got ${tools}" >&2; exit 1; }
[ "${size}" -le 5000 ] || { echo "tools/list exceeded 5000 B: ${size}" >&2; exit 1; }
echo "MCP tools/list OK: ${tools} tools, ${size} B <= 5000 B"

echo "[5/10] Verify cross-container memory persistence (remember -> recall)"
printf '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"footnote_remember","arguments":{"memories":[{"kind":"fact","scope":"footnote","text":"Docker smoke persistence marker %s","observed_at":"%s"}]}}}\n' "${MARKER}" "${TODAY}" \
  | docker run --rm -i "${HARDENED_ARGS[@]}" \
      -v "${STATE_VOL}:${STATE_DIR}" \
      "${IMAGE}" --db "${DB_PATH}" serve --mcp >/dev/null

recall_out="$(printf '{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"footnote_recall","arguments":{"query":"%s","mode":"lexical"}}}\n' "${MARKER}" \
  | docker run --rm -i "${HARDENED_ARGS[@]}" \
      -v "${STATE_VOL}:${STATE_DIR}" \
      "${IMAGE}" --db "${DB_PATH}" serve --mcp)"
echo "${recall_out}" | grep -q "${MARKER}" || {
  echo "Persistence recall failed: ${recall_out}" >&2
  exit 1
}

echo "[6/10] Verify FOOTNOTE_PATH_MAP Windows host cwd + footnote_code, and unmounted host transcript_path"
host_repo_json="${HOST_REPO//\\/\\\\}"
host_transcript_json="${HOST_TRANSCRIPT//\\/\\\\}"
path_map="${HOST_PREFIX}=${WORKSPACES_DIR}"
printf '{"hook_event_name":"SessionStart","session_id":"smoke-map","cwd":"%s","transcript_path":"%s"}\n' \
  "${host_repo_json}" "${host_transcript_json}" \
  | docker run --rm -i "${HARDENED_ARGS[@]}" \
      -e "FOOTNOTE_NO_LIVE_FETCH=1" \
      -e "FOOTNOTE_PATH_MAP=${path_map}" \
      -v "${STATE_VOL}:${STATE_DIR}" \
      -v "${REPO_MOUNT}:${WORKSPACES_DIR}/footnote:ro" \
      "${IMAGE}" hook >/dev/null

projects_out="$(docker run --rm "${HARDENED_ARGS[@]}" \
  -v "${STATE_VOL}:${STATE_DIR}" \
  "${IMAGE}" projects --quick)"
echo "${projects_out}" | grep -q '"agent":"claude"' || {
  echo "Unchanged host transcript_path did not preserve claude agent detection: ${projects_out}" >&2
  exit 1
}

stop_out="$(printf '{"hook_event_name":"Stop","session_id":"smoke-map","cwd":"%s","transcript_path":"%s"}\n' \
  "${host_repo_json}" "${host_transcript_json}" \
  | docker run --rm -i "${HARDENED_ARGS[@]}" \
      -e "FOOTNOTE_NO_LIVE_FETCH=1" \
      -e "FOOTNOTE_PATH_MAP=${path_map}" \
      -v "${STATE_VOL}:${STATE_DIR}" \
      -v "${REPO_MOUNT}:${WORKSPACES_DIR}/footnote:ro" \
      "${IMAGE}" hook)"
[ -z "${stop_out}" ] || {
  echo "Stop with an unmounted host transcript_path should not ask for a handoff: ${stop_out}" >&2
  exit 1
}
if docker run --rm "${HARDENED_ARGS[@]}" -v "${STATE_VOL}:${STATE_DIR}" --entrypoint test "${IMAGE}" -e "${STATE_DIR}/memory-hook/hook.log"; then
  echo "Stop with an unmounted host transcript_path wrote hook.log" >&2
  exit 1
fi

docker run --rm "${HARDENED_ARGS[@]}" \
  -v "${STATE_VOL}:${STATE_DIR}" \
  -v "${REPO_MOUNT}:${WORKSPACES_DIR}/footnote:ro" \
  "${IMAGE}" code-index "${WORKSPACES_DIR}/footnote" >/dev/null

code_out="$(printf '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"footnote_code","arguments":{"root":"%s","target":"map_host_path"}}}\n' "${host_repo_json}" \
  | docker run --rm -i "${HARDENED_ARGS[@]}" \
      -e "FOOTNOTE_PATH_MAP=${path_map}" \
      -v "${STATE_VOL}:${STATE_DIR}" \
      -v "${REPO_MOUNT}:${WORKSPACES_DIR}/footnote:ro" \
      "${IMAGE}" --db "${DB_PATH}" serve --mcp)"
echo "${code_out}" | grep -q "map_host_path" || {
  echo "Mapped footnote_code lookup failed: ${code_out}" >&2
  exit 1
}

echo "[7/10] Verify a mounted repository's .git/config cannot start a program (fsmonitor, filter driver)"
evil="${SCRATCH}/evil"
mkdir -p "${evil}"
evil_git="$(host_path "${evil}")" # host git is a Windows program under Git Bash
git -C "${evil_git}" init -q
printf 'print(1)\n' >"${evil}/app.py"
printf '* filter=smoke\n' >"${evil}/.gitattributes"
git -C "${evil_git}" -c user.name=smoke -c user.email=smoke@example.invalid add app.py .gitattributes
git -C "${evil_git}" -c user.name=smoke -c user.email=smoke@example.invalid commit -qm init
printf 'print(2)\n' >"${evil}/app.py" # stat-dirty: `status` would hash it through the filter
# Armed last: no git command runs on the host in this repository from here on.
git -C "${evil_git}" config core.fsmonitor "sh -c 'id > /tmp/footnote-smoke-ran' #"
git -C "${evil_git}" config filter.smoke.clean "sh -c 'id > /tmp/footnote-smoke-ran; cat' #"
printf '{"hook_event_name":"SessionStart","session_id":"smoke-evil","cwd":"%s/evil"}\n' "${WORKSPACES_DIR}" \
  | docker run --rm -i "${HARDENED_ARGS[@]}" \
      -e "FOOTNOTE_NO_LIVE_FETCH=1" \
      -v "${STATE_VOL}:${STATE_DIR}" \
      -v "${evil_git}:${WORKSPACES_DIR}/evil:ro" \
      --entrypoint sh "${IMAGE}" -c '
        footnote hook >/dev/null 2>&1
        footnote code-index /workspaces/evil >/dev/null 2>&1
        footnote projects >/dev/null 2>&1
        if [ -e /tmp/footnote-smoke-ran ]; then echo "repository config ran: $(cat /tmp/footnote-smoke-ran)" >&2; exit 1; fi' || {
  echo "A mounted repository started a program inside the container" >&2
  exit 1
}

echo "[8/10] Verify long-lived daemon mode + docker exec -i mcp proxy"
docker run -d --init --name "${DAEMON_NAME}" "${HARDENED_ARGS[@]}" \
  -e "FOOTNOTE_NO_LIVE_FETCH=1" \
  -v "${STATE_VOL}:${STATE_DIR}" \
  -v "${REPO_MOUNT}:${WORKSPACES_DIR}/footnote:ro" \
  "${IMAGE}" --db "${DB_PATH}" serve --mcp --daemon >/dev/null

ready=0
for _ in $(seq 1 30); do
  if docker exec "${DAEMON_NAME}" sh -c 'for s in "$FOOTNOTE_STATE_DIR"/footnote-*.sock; do [ -S "$s" ] && exit 0; done; exit 1'; then
    ready=1
    break
  fi
  sleep 0.2
done
[ "${ready}" = "1" ] || {
  echo "Daemon socket did not appear in time" >&2
  docker logs "${DAEMON_NAME}" >&2 || true
  exit 1
}

daemon_status="$(docker exec "${DAEMON_NAME}" footnote status)"
echo "${daemon_status}" | grep -q '"daemon_running":true' || {
  echo "Expected daemon_running:true in status: ${daemon_status}" >&2
  exit 1
}

exec_out="$(printf '%s\n{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"footnote_recall","arguments":{"query":"%s","mode":"lexical"}}}\n' \
  "${INIT}" "${MARKER}" \
  | docker exec -i "${DAEMON_NAME}" footnote --db "${DB_PATH}" mcp)"
echo "${exec_out}" | grep -q "${MARKER}" || {
  echo "Long-lived daemon exec proxy recall failed: ${exec_out}" >&2
  exit 1
}

echo "[9/10] Verify scripts/docker-agents.sh (MCP, hooks, legacy Gemini cleanup, JSONC, --home isolation, Docker-only --remove)"
agents_home="${SCRATCH}/home"
other_home="${SCRATCH}/other-home"
stub_bin="${SCRATCH}/bin"
mkdir -p "${agents_home}/.claude" "${agents_home}/.codex" "${agents_home}/.gemini/config" "${stub_bin}" \
  "${agents_home}/.t3/userdata/providers/antigravity/smoke1/config" \
  "${agents_home}/.t3/userdata/providers/antigravity/smoke-jsonc/config" \
  "${other_home}/.claude"
# A stub claude shadows any real one and prints the `claude mcp get` shape, and HOME points to the temporary home:
# the smoke suite never touches the machine's own agent configuration.
cat >"${stub_bin}/claude" <<'EOF'
#!/bin/sh
d="$(dirname "$0")"
echo "$*" >>"$d/claude-calls.log"
case "$1 $2" in
  "mcp get")
    [ -f "$d/claude-entry.txt" ] || exit 1
    cat "$d/claude-entry.txt"
    ;;
  "mcp add")
    while [ $# -gt 0 ] && [ "$1" != "--" ]; do shift; done
    [ "$1" = "--" ] && shift
    cmd="$1"; shift
    {
      echo "footnote-memory:"
      echo "  Scope: User config (available in all your projects)"
      echo "  Type: stdio"
      echo "  Command: ${cmd}"
      echo "  Args: $*"
    } >"$d/claude-entry.txt"
    ;;
  "mcp remove")
    rm -f "$d/claude-entry.txt"
    ;;
esac
EOF
chmod +x "${stub_bin}/claude"
# A glob in a string (Claude Code permissions) is not a JSON comment: hooks must still be added, permissions kept.
printf '%s\n' '{"permissions": {"allow": ["Read(src/**)"]}}' >"${agents_home}/.claude/settings.json"
# Gemini CLI settings file.
printf '{}\n' >"${agents_home}/.gemini/settings.json"
# A JSONC file with comments must be skipped and left byte-for-byte unchanged.
jsonc_file="${agents_home}/.t3/userdata/providers/antigravity/smoke-jsonc/config/mcp_config.json"
printf '// keep this comment\n{"mcpServers": {}}\n' >"${jsonc_file}"
agents() {
  env -u GEMINI_HOME -u CLAUDE_CONFIG_DIR -u CODEX_HOME -u FOOTNOTE_CONTAINER_NAME HOME="${agents_home}" PATH="${stub_bin}:${PATH}" \
    bash "${REPO_ROOT}/scripts/docker-agents.sh" --container "${DAEMON_NAME}" "$@"
}
agents_out="$(agents)"
echo "${agents_out}" | grep -q "answers over MCP with 8 tools" || {
  echo "docker-agents.sh did not verify the daemon: ${agents_out}" >&2
  exit 1
}
grep -q "mcp add --scope user footnote-memory -- .* exec -i ${DAEMON_NAME} footnote --db ${DB_PATH} mcp" \
  "${stub_bin}/claude-calls.log" || { echo "claude mcp add was not called as expected" >&2; exit 1; }
codex_toml="${agents_home}/.codex/config.toml"
grep -q '^\[mcp_servers.footnote-memory\]$' "${codex_toml}" || { echo "Codex entry missing" >&2; exit 1; }
registered_docker="$(sed -n 's/^command = "\(.*\)"$/\1/p' "${codex_toml}")"
agent_reply="$(printf '%s\n%s\n' "${INIT}" "${TOOLS_LIST}" \
  | "${registered_docker}" exec -i "${DAEMON_NAME}" footnote --db "${DB_PATH}" mcp | tail -n 1)"
[ "$(printf '%s' "${agent_reply}" | { grep -o '"inputSchema"' || true; } | wc -l | tr -d ' ')" = 8 ] || {
  echo "The registered command did not reach the daemon: ${agent_reply}" >&2
  exit 1
}
case "${registered_docker}" in *' '*) hook_command="\"${registered_docker}\" exec -i ${DAEMON_NAME} footnote hook" ;;
  *) hook_command="${registered_docker} exec -i ${DAEMON_NAME} footnote hook" ;; esac
if have_python; then
  python3 - "${agents_home}" "${registered_docker}" "${DAEMON_NAME}" "${hook_command}" "${jsonc_file}" <<'PY'
import json, sys
home, docker, container, hook, jsonc = sys.argv[1:]
load = lambda p: json.load(open(f"{home}/{p}", encoding="utf-8"))
mcp = ["exec", "-i", container, "footnote", "--db", "/state/memory.db", "mcp"]
for cfg in (".gemini/config", ".t3/userdata/providers/antigravity/smoke1/config"):
    entry = load(f"{cfg}/mcp_config.json")["mcpServers"]["footnote-memory"]
    assert entry == {"command": docker, "args": mcp}, (cfg, entry)
    agy = load(f"{cfg}/hooks.json")["footnote-memory"]
    assert {k: [(h["command"], h["timeout"]) for h in v] for k, v in agy.items()} == {
        "SessionStart": [(hook, 15)], "PreInvocation": [(hook, 10)], "Stop": [(hook, 5)]}, (cfg, agy)
for f in (".claude/settings.json", ".codex/hooks.json"):
    hooks = load(f)["hooks"]
    got = {ev: [(h["command"], h["timeout"]) for g in hooks[ev] for h in g["hooks"]] for ev in hooks}
    assert got == {"SessionStart": [(hook, 15)], "UserPromptSubmit": [(hook, 10)], "Stop": [(hook, 5)]}, (f, got)
assert open(f"{home}/.gemini/settings.json", encoding="utf-8").read() == "{}\n"
assert load(".claude/settings.json")["permissions"] == {"allow": ["Read(src/**)"]}
assert open(jsonc, encoding="utf-8").read() == '// keep this comment\n{"mcpServers": {}}\n'
PY
  [ "$(agents | grep -c 'already registered')" -ge 8 ] || { echo "a second run changed the registration" >&2; exit 1; }
fi
# The registered hook command, run through a shell as an agent runs it, answers a session start with the memory pack.
hook_out="$(printf '{"hook_event_name":"SessionStart","session_id":"smoke-hook","cwd":"%s/footnote"}\n' "${WORKSPACES_DIR}" \
  | bash -c "${hook_command}")" || { echo "The registered hook command failed" >&2; exit 1; }
echo "${hook_out}" | grep -q "${MARKER}" || { echo "The hook did not return the memory pack: ${hook_out}" >&2; exit 1; }

# --home pointing elsewhere than $HOME must skip `claude mcp` and never call claude.
calls_before="$(wc -l <"${stub_bin}/claude-calls.log" | tr -d ' ')"
home_out="$(agents --home "${other_home}")"
calls_after="$(wc -l <"${stub_bin}/claude-calls.log" | tr -d ' ')"
[ "${calls_before}" = "${calls_after}" ] || { echo "--home invoked claude mcp unexpectedly" >&2; exit 1; }
echo "${home_out}" | grep -q "skipped: --home cannot guarantee" || { echo "--home did not explain claude mcp skip: ${home_out}" >&2; exit 1; }

# --remove also takes out settings left by older Gemini CLI registrations.
if have_python; then
  python3 - "${agents_home}/.gemini/settings.json" "${registered_docker}" "${DAEMON_NAME}" "${hook_command}" <<'PY'
import json, sys
path, docker, container, hook = sys.argv[1:]
with open(path, "w", encoding="utf-8") as f:
    json.dump({
        "mcpServers": {"footnote-memory": {"command": docker, "args": ["exec", "-i", container, "footnote", "--db", "/state/memory.db", "mcp"]}},
        "hooks": {"BeforeAgent": [{"matcher": "*", "hooks": [{"type": "command", "command": hook, "timeout": 10000}]}]},
    }, f)
PY
fi
agents --remove >/dev/null
if have_python && grep -q 'footnote-memory' "${agents_home}/.gemini/settings.json"; then
  echo "--remove left the Gemini CLI Docker MCP entry" >&2
  exit 1
fi
[ ! -f "${stub_bin}/claude-entry.txt" ] || { echo "--remove left the Claude Code Docker MCP entry" >&2; exit 1; }
if grep -q 'footnote-memory' "${codex_toml}"; then echo "--remove left the Codex entry" >&2; exit 1; fi
if have_python && grep -q 'footnote hook' "${agents_home}/.claude/settings.json" "${agents_home}/.codex/hooks.json" \
  "${agents_home}/.gemini/settings.json" "${agents_home}/.gemini/config/hooks.json"; then
  echo "--remove left a Docker memory hook" >&2
  exit 1
fi

# --remove must leave native `footnote` MCP entries and native memory hooks untouched.
cat >"${stub_bin}/claude-entry.txt" <<'EOF'
footnote-memory:
  Scope: User config (available in all your projects)
  Type: stdio
  Command: /usr/local/bin/footnote
  Args: --db /state/memory.db mcp
EOF
cat >"${codex_toml}" <<'EOF'
[mcp_servers.footnote-memory]
command = "/usr/local/bin/footnote"
args = ["--db", "/state/memory.db", "mcp"]
EOF
if have_python; then
  printf '%s\n' '{"hooks":{"SessionStart":[{"hooks":[{"type":"command","command":"/usr/local/bin/footnote hook","timeout":15}]}]}}' \
    >"${agents_home}/.claude/settings.json"
  printf '%s\n' '{"mcpServers":{"footnote-memory":{"command":"/usr/local/bin/footnote","args":["--db","/state/memory.db","mcp"]}},"hooks":{"SessionStart":[{"matcher":"*","hooks":[{"type":"command","command":"/usr/local/bin/footnote hook","timeout":15000}]}]}}' \
    >"${agents_home}/.gemini/settings.json"
  printf '%s\n' '{"mcpServers":{"footnote-memory":{"command":"/usr/local/bin/footnote","args":["--db","/state/memory.db","mcp"]}}}' \
    >"${agents_home}/.gemini/config/mcp_config.json"
  printf '%s\n' '{"footnote-memory":{"SessionStart":[{"type":"command","command":"/usr/local/bin/footnote hook","timeout":15}]}}' \
    >"${agents_home}/.gemini/config/hooks.json"
fi
native_out="$(agents --remove)"
echo "${native_out}" | grep -q "left alone (not a Docker entry)" || {
  echo "--remove did not report leaving native entries alone: ${native_out}" >&2
  exit 1
}
[ -f "${stub_bin}/claude-entry.txt" ] || { echo "--remove deleted a native Claude Code MCP entry" >&2; exit 1; }
grep -q '^\[mcp_servers.footnote-memory\]$' "${codex_toml}" || { echo "--remove deleted a native Codex MCP entry" >&2; exit 1; }
if have_python; then
  grep -q '/usr/local/bin/footnote hook' "${agents_home}/.claude/settings.json" || { echo "--remove deleted a native Claude hook" >&2; exit 1; }
  grep -q '"/usr/local/bin/footnote"' "${agents_home}/.gemini/settings.json" || { echo "--remove deleted a native Gemini MCP entry" >&2; exit 1; }
  grep -q '/usr/local/bin/footnote hook' "${agents_home}/.gemini/settings.json" || { echo "--remove deleted a native Gemini hook" >&2; exit 1; }
  grep -q '"/usr/local/bin/footnote"' "${agents_home}/.gemini/config/mcp_config.json" || { echo "--remove deleted a native Antigravity MCP entry" >&2; exit 1; }
  grep -q '/usr/local/bin/footnote hook' "${agents_home}/.gemini/config/hooks.json" || { echo "--remove deleted a native Antigravity hook" >&2; exit 1; }
fi

echo "[10/10] All Docker smoke checks passed."
