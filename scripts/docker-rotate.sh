#!/usr/bin/env bash
# Rotate the Compose daemon to a new image without interrupting the agents that use it (#392).
#
# Agents reach the daemon as `docker exec -i footnote ...`. Their MCP sessions are long-lived processes inside the
# container, and the daemon socket in the state volume is where every new connection lands. `docker compose up -d`
# recreates the container, which ends every open session. This script instead:
#   1. Proves the new image away from the live stack: the smoke test, then the live Compose settings on a copy of the
#      state volume. The previous image runs there first with a session open, then the new one starts next to it.
#      Checks: MCP, recall with the installed models, the memory hook, status, and the previous session still answering.
#      Then the previous daemon stops, and the new one must still serve, with the audit chain intact.
#   2. Starts the new daemon next to the live one, on the live volume, and checks that it serves.
#   3. Moves the container name over one Docker API connection, so `docker exec footnote` never finds no container.
#   4. Leaves the previous container serving the sessions it already has. It stops once they have ended, and the
#      new daemon is checked again after the stop.
# If a check fails before the name moves, the new container is removed and the previous daemon takes the socket back.
#
#   docker build -t footnote:next .
#   bash scripts/docker-rotate.sh --image footnote:next                # prove, switch, report the sessions left
#   bash scripts/docker-rotate.sh --image footnote:next --drain 3600   # ... and wait up to an hour for them to end
#   bash scripts/docker-rotate.sh --image footnote:next --auto-stop    # ... or let the previous container stop itself
#   bash scripts/docker-rotate.sh --finish [--drain SECONDS] [--force] # later: stop and remove the previous container
#
# Rollback: the image that was live keeps the tag <repository>:previous. Rotate to it the same way.
# Settings come from compose.yaml and .env, as for `docker compose up`. The live container stays in the Compose project
# where it was created (`<project>` and `<project>-b` take turns), so later Compose commands need
# `docker compose -p <that project>`. The script prints the project name.
# The name swap runs a short-lived helper from the new image with the Docker socket mounted (the same access as the
# docker CLI). Set DOCKER_SOCK if the engine socket is not /var/run/docker.sock. Without the helper, two `docker rename`
# calls leave a gap of about 100 ms.
set -euo pipefail
export MSYS_NO_PATHCONV=1 MSYS2_ARG_CONV_EXCL='*'
SELF="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/$(basename "${BASH_SOURCE[0]}")"
cd "$(dirname "$SELF")/.."

IMAGE=""
DRAIN=0
AUTO_STOP=0
FINISH=0
FORCE=0
SKIP_SMOKE=0
usage() { sed -n '2,/^set -euo/p' "$SELF" | sed '$d; s/^# \{0,1\}//'; exit "${1:-0}"; }
while [ $# -gt 0 ]; do
  case "$1" in
    --image) IMAGE="$2"; shift 2 ;;
    --drain) DRAIN="$2"; shift 2 ;;
    --auto-stop) AUTO_STOP=1; shift ;;
    --finish) FINISH=1; shift ;;
    --force) FORCE=1; shift ;;
    --skip-smoke) SKIP_SMOKE=1; shift ;;
    -h|--help) usage 0 ;;
    *) echo "unknown option: $1" >&2; usage 2 >&2 ;;
  esac
done

say() { printf '\n== %s\n' "$*"; }
ok() { printf '  ok    %s\n' "$*"; }
info() { printf '  ..    %s\n' "$*"; }
die() { printf '  FAIL  %s\n' "$*" >&2; exit 1; }
trimcr() { tr -d '\r'; }

# --- Settings, read the way Compose reads them -------------------------------------------------------------------------
CONFIG="$(docker compose config 2>/dev/null | trimcr)" || die "docker compose config failed (is FOOTNOTE_WORKSPACES set?)"
BASE_PROJECT="$(printf '%s\n' "$CONFIG" | sed -n 's/^name: //p' | sed -n 1p)"
NAME="$(printf '%s\n' "$CONFIG" | sed -n 's/^ *container_name: //p' | sed -n 1p)"
IMG_REF="$(printf '%s\n' "$CONFIG" | awk '/^  footnote:$/{s=1} s && /^    image: /{print $2; exit}')"
CONF_VOL="$(printf '%s\n' "$CONFIG" | awk '/^volumes:$/{v=1} v && /^  footnote-state:$/{s=1} s && /^    name: /{print $2; exit}')"
PREV="$NAME-previous"
NEXT="$NAME-next"
REPO="${IMG_REF%:*}"
DOCKER_SOCK="${DOCKER_SOCK:-/var/run/docker.sock}"
LOG="${TMPDIR:-/tmp}/footnote-rotate.log"
: > "$LOG"
INIT='{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"docker-rotate","version":"1"}}}'
INITED='{"jsonrpc":"2.0","method":"notifications/initialized"}'
HEALTH='{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"footnote_info","arguments":{"op":"health"}}}'
TOOLS='{"jsonrpc":"2.0","id":3,"method":"tools/list","params":{}}'
RECALL='{"jsonrpc":"2.0","id":4,"method":"tools/call","params":{"name":"footnote_recall","arguments":{"query":"docker daemon rotation check","mode":"hybrid","limit":2}}}'

exists() { docker container inspect "$1" >/dev/null 2>&1; }
running() { [ "$(docker container inspect -f '{{.State.Running}}' "$1" 2>/dev/null | trimcr)" = true ]; }
cid() { docker container inspect -f '{{.Id}}' "$1" 2>/dev/null | trimcr; }
db_of() { docker container inspect -f '{{json .Config.Cmd}}' "$1" 2>/dev/null | trimcr | sed -n 's/.*"--db","\([^"]*\)".*/\1/p'; }
state_vol_of() { docker container inspect -f '{{range .Mounts}}{{if eq .Destination "/state"}}{{.Name}}{{end}}{{end}}' "$1" | trimcr; }
project_of() { docker container inspect -f '{{index .Config.Labels "com.docker.compose.project"}}' "$1" | trimcr; }
version_of_image() { docker run --rm --network none "$1" --version | trimcr | awk '{print $2}'; }
# Listening Unix sockets in a container's own network namespace: the daemon that container runs.
listeners() { docker exec "$1" sh -c "grep -E ' 00010000 0001 01 [0-9]+ /' /proc/net/unix | awk '{print \$8}'" 2>/dev/null | trimcr; }
listens_on() { local l; l="$(listeners "$1")"; [[ $'\n'"$l"$'\n' == *$'\n'"$2"$'\n'* ]]; }
inode_of() { docker exec "$1" stat -c %i "$2" 2>/dev/null | trimcr; }
# One MCP session through `footnote mcp`, as an agent opens it. Prints the replies. Stdin stays open until the last
# request has its reply (60 s at most), as an agent's does: on stdin EOF the proxy waits only 3 s for pending replies,
# and the first hybrid recall of a cold daemon loads the models.
mcp() {
  local c="$1"; shift
  local last f i; last="$(printf '%s\n' "${@: -1}" | sed -n 's/.*"id":\([0-9]*\).*/\1/p')"
  f="$(mktemp)"
  { printf '%s\n' "$INIT" "$INITED" "$@"
    for i in $(seq 1 120); do grep -q "\"id\":$last[,}]" "$f" 2>/dev/null && break; sleep 0.5; done
  } | docker exec -i "$c" footnote --db "$DB" mcp > "$f" 2>&1 || true
  trimcr < "$f"; rm -f "$f"
}
served_by() { sed -n 's/.*"serverInfo":{[^}]*"version":"\([^"]*\)".*/\1/p' | sed -n 1p; }
answered() { # replies id: a result for that id, not an error
  local line; line="$(printf '%s\n' "$1" | sed -n "/\"id\":$2[,}]/{p;q;}")"
  [ -n "$line" ] && [[ "$line" != *'"isError":true'* ]] && [[ "$line" != *'"error":{'* ]]
}
check_serving() { # container expected_version label
  local out v
  out="$(mcp "$1" "$HEALTH" "$TOOLS" "$RECALL")"
  v="$(printf '%s\n' "$out" | served_by)"
  [[ "$out" != *'no shared daemon'* ]] || die "$3: the session fell back to an in-process server (no daemon on the socket)"
  [ "$v" = "$2" ] || die "$3: served by version '${v:-none}', expected $2"
  answered "$out" 2 || die "$3: footnote_info health failed: ${out:0:400}"
  answered "$out" 3 || die "$3: tools/list failed"
  answered "$out" 4 || die "$3: hybrid recall failed: ${out:0:400}"
  ok "$3: MCP health, tools/list and hybrid recall answered by $v"
}
check_hook() {
  local cwd; cwd="$( (pwd -W 2>/dev/null || pwd) | sed 's#/#\\\\#g')"
  [[ "$cwd" == ?:* ]] || cwd="$(pwd)"
  printf '{"hook_event_name":"UserPromptSubmit","session_id":"docker-rotate","cwd":"%s","prompt":"docker daemon rotation check"}\n' "$cwd" \
    | docker exec -i "$1" footnote hook >/dev/null 2>&1 || die "$2: the memory hook failed"
  ok "$2: memory hook"
}
check_status() {
  local s; s="$(docker exec "$1" footnote --db "$DB" status 2>/dev/null || true)"
  [[ "$s" =~ \"daemon_running\":\ *true ]] || die "$2: status does not see the daemon"
  ok "$2: status sees the daemon"
}
audit_ok() { docker exec "$1" footnote audit verify --file "$STATE_DIR/audit.jsonl" --mac-key "$STATE_DIR/audit.key" >/dev/null 2>&1; }
# Client sessions in a container: top-level `docker exec` processes other than a daemon (their parent is outside it).
# Fails, rather than printing nothing, when the processes cannot be listed: an empty list means "safe to stop".
sessions() {
  local top; top="$(docker top "$1" -eo pid,ppid,etime,args 2>/dev/null | trimcr)" || return 1
  [ -n "$top" ] || return 1
  printf '%s\n' "$top" | tail -n +2 | awk '
    { ppid[NR]=$2; line[NR]=$0; inside[$1]=1 }
    END { for (i=1; i<=NR; i++) if (!(ppid[i] in inside) && line[i] !~ /docker-init/ && line[i] !~ / serve .*--daemon/ \
          && line[i] !~ /footnote-rotate-watch/) print line[i] }'
}

# --- The name swap ------------------------------------------------------------------------------------------------------
# A helper talks to the engine directly. One process renames the live container away. Another one, started first,
# keeps asking for the freed name in pipelined bursts on one connection; the engine answers 409 while the name is taken.
# The window where no container holds the name is then the engine's time for one refused rename, not a rename's work
# (about 25 ms), one request round trip (a few ms), or two docker CLI start-ups (about 270 ms measured).
helper_ok() {
  docker run --rm --network none -u 0 --entrypoint perl -v "$DOCKER_SOCK:/var/run/docker.sock" "$1" -MIO::Socket::UNIX -e '
    my $s = IO::Socket::UNIX->new(Peer => "/var/run/docker.sock") or exit 1;
    print $s "GET /_ping HTTP/1.1\r\nHost: docker\r\nConnection: close\r\n\r\n"; local $/; exit(<$s> =~ m{^HTTP/1\.[01] 200} ? 0 : 1);' 2>/dev/null
}
swap_names() { # helper_image name name_for_its_holder container_to_get_it  ->  prints both HTTP statuses
  local taker_id; taker_id="$(cid "$4")"; [ -n "$taker_id" ] || { echo "no container $4"; return 1; }
  docker run --rm --network none -u 0 --entrypoint perl -v "$DOCKER_SOCK:/var/run/docker.sock" "$1" \
    -MIO::Socket::UNIX -MTime::HiRes=time -e '
    my ($live, $prev, $taker) = @ARGV;
    sub conn { IO::Socket::UNIX->new(Peer => "/var/run/docker.sock") }
    sub statuses { # read $n HTTP responses from $s, return their status codes
      my ($s, $n) = @_; my (@st, $buf); $buf = "";
      while (@st < $n) {
        while ($buf !~ /\r\n\r\n/) { sysread($s, $buf, 65536, length $buf) or return @st }
        my ($head, $rest) = split /\r\n\r\n/, $buf, 2;
        my ($code) = $head =~ m{^HTTP/1\.[01] (\d{3})};
        if ($head =~ /\r\nTransfer-Encoding: *chunked/i) {
          until ($rest =~ /(?:^|\r\n)0\r\n\r\n/) { sysread($s, $rest, 65536, length $rest) or return @st }
          $buf = $'"'"'; } else {
          my ($len) = $head =~ /\r\nContent-Length: *(\d+)/i; $len //= 0;
          while (length($rest) < $len) { sysread($s, $rest, 65536, length $rest) or return @st }
          $buf = substr($rest, $len); }
        push @st, $code;
      }
      return @st;
    }
    pipe(my $rd, my $wr) or die "pipe: $!\n";
    my $pid = fork() // die "fork: $!\n";
    if (!$pid) {   # takes the name the moment the engine frees it
      close $rd; my $s = conn() or exit 2; my ($tries, $end) = (0, time + 10);
      my $ask = "POST /containers/$taker/rename?name=$live HTTP/1.1\r\nHost: docker\r\nContent-Length: 0\r\n\r\n";
      syswrite $wr, "r";
      while (time < $end && $tries < 20000) {
        print $s ($ask x 25); my @st = statuses($s, 25); $tries += @st;
        if (grep { $_ == 204 } @st) { print "204 after $tries tries\n"; exit 0 }
        my @bad = grep { $_ != 409 } @st; if (@bad) { print "$bad[0] after $tries tries\n"; exit 1 }
        if (@st < 25) { $s = conn() or exit 2 }
      }
      print "gave up after $tries tries\n"; exit 1;
    }
    close $wr; sysread $rd, my $ready, 1;   # the taker is running before the name is freed
    my $s = conn() or die "docker socket: $!\n";
    print $s "POST /containers/$live/rename?name=$prev HTTP/1.1\r\nHost: docker\r\nContent-Length: 0\r\nConnection: close\r\n\r\n";
    my ($first) = statuses($s, 1);
    waitpid($pid, 0);
    print "$first ", ($? >> 8 ? "failed" : "ok"), "\n";' "$2" "$3" "$taker_id" | trimcr | tr '\n' ' '
}

# --- Finish: stop and remove the previous container once it has no session left -------------------------------------------
finish() {
  exists "$PREV" || { ok "no previous container ($PREV): nothing to finish"; return 0; }
  exists "$NAME" && running "$NAME" || die "$NAME is not running: not stopping $PREV"
  DB="$(db_of "$NAME")"; STATE_DIR="$(dirname "$DB")"
  local sock version; version="$(docker exec "$NAME" footnote --version | trimcr | awk '{print $2}')"
  sock="$(listeners "$NAME" | sed -n '/\/footnote-[0-9a-f]*\.sock$/{p;q;}')"
  [ -n "$sock" ] || die "$NAME has no daemon listening"
  if running "$PREV"; then
    say "Drain $PREV (sessions it still serves)"
    local waited=0 left
    while :; do
      left="$(sessions "$PREV")" || die "cannot list the processes of $PREV: not stopping it"
      [ -z "$left" ] && break
      if [ "$FORCE" = 1 ]; then info "--force: ending $(printf '%s\n' "$left" | wc -l | tr -d ' ') session(s)"; break; fi
      if [ "$waited" -ge "$DRAIN" ]; then
        info "still serving:"; printf '%s\n' "$left" | sed 's/^/          /'
        info "$PREV keeps them; run again later: bash scripts/docker-rotate.sh --finish [--drain SECONDS] [--force]"
        return 0
      fi
      sleep 10; waited=$((waited + 10))
    done
    ok "$PREV has no session left"
    say "Take $PREV down"
    listens_on "$NAME" "$sock" || die "$NAME no longer listens on $sock: keeping $PREV"
    audit_ok "$NAME" && local audit_before=1 || local audit_before=0
    docker stop -t 30 "$PREV" >/dev/null
  else
    say "$PREV already stopped"
    local audit_before=1
  fi
  listens_on "$NAME" "$sock" || die "$NAME stopped listening after $PREV went down"
  docker exec "$NAME" test -S "$sock" || die "the socket file $sock is gone"
  ok "$NAME still listens on $sock"
  check_serving "$NAME" "$version" "$NAME after $PREV went down"
  check_status "$NAME" "$NAME"
  if audit_ok "$NAME"; then ok "audit chain verifies (both daemons appended to it)"
  elif [ "$audit_before" = 0 ]; then info "audit chain did not verify before the stop either: not caused by the rotation"
  else die "audit chain no longer verifies"; fi
  docker rm "$PREV" >/dev/null
  ok "$PREV removed; the previous image keeps the tag $REPO:previous"
}

if [ "$FINISH" = 1 ]; then finish; exit 0; fi

# --- Preconditions -------------------------------------------------------------------------------------------------------
[ -n "$IMAGE" ] || die "--image is required (for example: docker build -t footnote:next . && $0 --image footnote:next)"
say "Preconditions"
running "$NAME" || die "$NAME is not running: start it with docker compose up -d, there is nothing to rotate"
for c in "$PREV" "$NEXT"; do exists "$c" && die "$c exists: finish the last rotation first (--finish) or remove it"; done
NEW_ID="$(docker image inspect -f '{{.Id}}' "$IMAGE" 2>/dev/null | trimcr)" || die "image $IMAGE not found"
LIVE_IMG_ID="$(docker container inspect -f '{{.Image}}' "$NAME" | trimcr)"
[ "$NEW_ID" != "$LIVE_IMG_ID" ] || die "$NAME already runs $IMAGE"
LIVE_PROJECT="$(project_of "$NAME")"
LIVE_VOL="$(state_vol_of "$NAME")"
[ "$LIVE_VOL" = "$CONF_VOL" ] || die "$NAME uses volume $LIVE_VOL but Compose would mount $CONF_VOL: set FOOTNOTE_STATE_VOLUME=$LIVE_VOL in .env"
DB="$(db_of "$NAME")"; [ -n "$DB" ] || die "cannot read --db from $NAME"
STATE_DIR="$(dirname "$DB")"
if [ "$LIVE_PROJECT" = "$BASE_PROJECT" ]; then NEXT_PROJECT="$BASE_PROJECT-b"; else NEXT_PROJECT="$BASE_PROJECT"; fi
[ -z "$(docker ps -aq --filter "label=com.docker.compose.project=$NEXT_PROJECT" --filter label=com.docker.compose.service=footnote)" ] \
  || die "Compose project $NEXT_PROJECT already has a footnote container"
SOCK="$(listeners "$NAME" | awk -v d="$STATE_DIR/footnote-" 'index($0, d) == 1 && /\.sock$/ {print; exit}')"
[ -n "$SOCK" ] || die "$NAME has no daemon listening in $STATE_DIR"
OLD_VERSION="$(docker exec "$NAME" footnote --version | trimcr | awk '{print $2}')"
NEW_VERSION="$(version_of_image "$IMAGE")"
OLD_REF_ID="$(docker image inspect -f '{{.Id}}' "$IMG_REF" 2>/dev/null | trimcr || true)"
ok "live: $NAME ($OLD_VERSION, project $LIVE_PROJECT, volume $LIVE_VOL, socket $SOCK)"
ok "next: $IMAGE ($NEW_VERSION), will run as $NAME in project $NEXT_PROJECT"
[ "$OLD_VERSION" != "$NEW_VERSION" ] || info "same version string: the checks tell the daemons apart by their sockets only"
if helper_ok "$IMAGE"; then SWAP=api; ok "name swap over the Docker API ($DOCKER_SOCK)"
else SWAP=cli; info "Docker socket helper unavailable: two docker rename calls (about 100 ms without the name)"; fi
docker tag "$LIVE_IMG_ID" "$REPO:previous"
ok "rollback tag: $REPO:previous"

# --- 1. Prove the new image away from the live stack ---------------------------------------------------------------------
TEST_PROJECT="$BASE_PROJECT-rotate-test"
COPY_VOL="$LIVE_VOL-rotate-test"
TP="$NAME-rotate-prev"; TN="$NAME-rotate-next"
test_down() {
  docker rm -f "$TP" "$TN" >/dev/null 2>&1 || true
  docker volume rm -f "$COPY_VOL" >/dev/null 2>&1 || true
}
test_up() { # container image
  FOOTNOTE_CONTAINER_NAME="$1" FOOTNOTE_IMAGE="$2" FOOTNOTE_STATE_VOLUME="$COPY_VOL" \
    docker compose -p "$TEST_PROJECT-$1" up -d --no-build footnote >>"$LOG" 2>&1 || die "docker compose up $1 failed (see $LOG)"
}
wait_listening() { local i; for i in $(seq 1 60); do listens_on "$1" "$2" && return 0; sleep 1; done; return 1; }
trap test_down EXIT
test_down

if [ "$SKIP_SMOKE" = 0 ]; then
  say "1a. Smoke test of $IMAGE (isolated volume)"
  bash scripts/docker-smoke.sh "$IMAGE" > "${TMPDIR:-/tmp}/footnote-rotate-smoke.log" 2>&1 \
    || die "smoke test failed: ${TMPDIR:-/tmp}/footnote-rotate-smoke.log"
  ok "smoke test passed"
fi

say "1b. The live settings on a copy of $LIVE_VOL"
docker volume create "$COPY_VOL" >/dev/null
docker run --rm -u 0 --network none --entrypoint sh -v "$LIVE_VOL:/src:ro" -v "$COPY_VOL:/dst" "$IMAGE" \
  -c 'cd /src && tar cf - --exclude="./*.sock" . | (cd /dst && tar xpf -)'
ok "copied ($(docker run --rm --network none --entrypoint du -v "$COPY_VOL:/v:ro" "$IMAGE" -sh /v | trimcr | cut -f1))"
test_up "$TP" "$REPO:previous"
wait_listening "$TP" "$SOCK" || die "the previous image's daemon does not listen on the copy"
coproc HELD { docker exec -i "$TP" footnote --db "$DB" mcp 2>/dev/null; }
printf '%s\n' "$INIT" >&"${HELD[1]}"; read -r -t 30 line <&"${HELD[0]}" || die "no reply from a session on the previous image"
printf '%s\n' "$INITED" >&"${HELD[1]}"
ok "a session is open on the previous image ($(printf '%s' "$line" | served_by))"
test_up "$TN" "$IMAGE"
wait_listening "$TN" "$SOCK" || die "the new daemon does not listen on the copy"
check_serving "$TN" "$NEW_VERSION" "new image on the copy"
check_hook "$TN" "new image on the copy"
check_status "$TN" "new image on the copy"
printf '%s\n' "$RECALL" >&"${HELD[1]}"; read -r -t 60 line <&"${HELD[0]}" || die "the previous session stopped answering"
answered "$line" 4 || die "the previous image cannot read the database the new one opened: ${line:0:400}"
ok "the session on the previous image still answers, on the database the new image opened"
eval "exec ${HELD[1]}>&-"; wait "$HELD_PID" 2>/dev/null || true
docker stop -t 30 "$TP" >/dev/null
listens_on "$TN" "$SOCK" || die "the new daemon lost its socket when the previous one stopped"
check_serving "$TN" "$NEW_VERSION" "new image after the previous one went down"
audit_ok "$TN" || die "the audit chain does not verify after both daemons wrote to it"
ok "audit chain verifies after both daemons wrote to it"
test_down
trap - EXIT

# --- 2. Start the new daemon next to the live one --------------------------------------------------------------------------
say "2. Start $NEXT on $LIVE_VOL"
BEFORE_INODE="$(inode_of "$NAME" "$SOCK")"
audit_ok "$NAME" && AUDIT_BEFORE=1 || AUDIT_BEFORE=0
fallback() { # $1: why. Puts the previous daemon back in charge of the socket, keeps its sessions.
  printf '  FAIL  %s\n' "$1" >&2
  printf '  ..    rolling back\n' >&2
  if [ -n "$NEXT_CID" ] && [ "$(cid "$NAME")" = "$NEXT_CID" ] && exists "$PREV"; then
    if [ "$SWAP" = api ]; then swap_names "$IMAGE" "$NAME" "$NEXT" "$PREV" >/dev/null || true; fi
    [ "$(cid "$NAME")" = "$NEXT_CID" ] && docker rename "$NAME" "$NEXT" && docker rename "$PREV" "$NAME"
  fi
  docker rm -f "$NEXT" >/dev/null 2>&1 || true
  if [ -n "$OLD_REF_ID" ]; then docker tag "$OLD_REF_ID" "$IMG_REF"; fi
  if [ "$(inode_of "$NAME" "$SOCK")" != "$BEFORE_INODE" ]; then
    # The new daemon replaced the socket file: start a second daemon in the previous container to take it back.
    local taken
    taken="$(inode_of "$NAME" "$SOCK")"
    docker exec -d "$NAME" footnote --db "$DB" serve --mcp --daemon
    local i; for i in $(seq 1 30); do [ "$(inode_of "$NAME" "$SOCK")" != "$taken" ] && break; sleep 1; done
    printf '  ..    restart %s at a quiet moment to go back to a single daemon\n' "$NAME" >&2
  fi
  docker update --restart=unless-stopped "$NAME" >/dev/null 2>&1 || true
  printf '  ..    %s serves new connections again with %s; its sessions were kept\n' "$NAME" "$OLD_VERSION" >&2
  exit 1
}
docker tag "$NEW_ID" "$IMG_REF"
FOOTNOTE_CONTAINER_NAME="$NEXT" docker compose -p "$NEXT_PROJECT" up -d --no-build footnote >>"$LOG" 2>&1 \
  || { NEXT_CID=""; NEXT_INODE=""; fallback "docker compose up $NEXT failed (see $LOG)"; }
NEXT_CID="$(cid "$NEXT")"; NEXT_INODE=""
wait_listening "$NEXT" "$SOCK" || fallback "$NEXT does not listen on $SOCK"
NEXT_INODE="$(inode_of "$NEXT" "$SOCK")"
[ "$NEXT_INODE" != "$BEFORE_INODE" ] || fallback "the socket file did not change: another daemon still owns it"
ok "$NEXT listens; new connections reach it from here on"
( check_serving "$NEXT" "$NEW_VERSION" "$NEXT on the live volume" ) || fallback "$NEXT does not serve"

# --- 3. Move the name -------------------------------------------------------------------------------------------------------
say "3. Move the name $NAME"
if [ "$SWAP" = api ]; then
  statuses="$(swap_names "$IMAGE" "$NAME" "$PREV" "$NEXT" || true)"
else
  docker rename "$NAME" "$PREV" && docker rename "$NEXT" "$NAME" && statuses="204 204" || statuses="cli failed"
fi
if [ "$(cid "$NAME")" != "$NEXT_CID" ]; then
  # Never leave the name empty: whatever happened, give it back to the previous container.
  exists "$NAME" || { exists "$PREV" && docker rename "$PREV" "$NAME"; }
  fallback "the name swap failed ($statuses)"
fi
docker update --restart=no "$PREV" >/dev/null
ok "$NAME is now the new container ($statuses); $PREV keeps its sessions and will not restart"
( check_serving "$NAME" "$NEW_VERSION" "$NAME after the swap"; check_status "$NAME" "$NAME" ) || fallback "$NAME does not serve after the swap"
[ "$(docker exec "$NAME" footnote --version | trimcr | awk '{print $2}')" = "$NEW_VERSION" ] || fallback "docker exec $NAME does not run the new binary"
ok "docker exec $NAME runs $NEW_VERSION"

# --- 4. The previous container -----------------------------------------------------------------------------------------------
if [ "$AUTO_STOP" = 1 ] && [ "$DRAIN" = 0 ]; then
  # Inside the previous container: once no footnote client process is left, stop its daemons (the container then exits).
  # Daemons include those the memory hook starts on demand (`/usr/local/bin/footnote ... serve --mcp --daemon`).
  docker exec -d "$PREV" sh -c '
    while :; do
      n=0
      for p in /proc/[0-9]*; do
        c=$(tr "\0" " " < "$p/cmdline" 2>/dev/null) || continue
        case "$c" in *"footnote "*serve*--daemon*|*docker-init*) ;; "footnote "*|*/footnote\ *) n=$((n+1)) ;; esac
      done
      [ "$n" -eq 0 ] && break
      sleep 30
    done
    for p in /proc/[0-9]*; do
      case "$(tr "\0" " " < "$p/cmdline" 2>/dev/null)" in *docker-init*) ;; *"footnote "*serve*--daemon*) kill -TERM "${p#/proc/}" ;; esac
    done' footnote-rotate-watch
  say "4. $PREV stops by itself when its last session ends"
  info "then check and remove it: bash scripts/docker-rotate.sh --finish"
else
  finish
fi
say "Done: $NAME runs $NEW_VERSION (project $NEXT_PROJECT; Compose commands: docker compose -p $NEXT_PROJECT ...)"
