// The words for a commit request sent from the window (`footnote agent-ask`, #501): which agent session it is meant for,
// and who took it and when. Pure, so `npm test` checks them without the app.

const AGENT_NAMES = { claude: "Claude Code", codex: "Codex", antigravity: "Antigravity" };
const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

/** `Claude Code session 3f2a1b9c`, `Codex`, or null when the engine knew neither the agent nor the session. */
export function sessionName(agent, session) {
  const who = AGENT_NAMES[agent] || agent || "";
  const id = session && session !== "unknown" ? String(session).slice(0, 8) : "";
  if (!who && !id) return null;
  return id ? `${who || "Agent"} session ${id}` : who;
}

/** `14:05` today, else `22 Nov, 14:05`, from a Unix time in seconds, in local time. */
export function clock(unix, now = new Date()) {
  const d = new Date(unix * 1000);
  const hm = `${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;
  const sameDay = d.getFullYear() === now.getFullYear() && d.getMonth() === now.getMonth() && d.getDate() === now.getDate();
  return sameDay ? hm : `${d.getDate()} ${MONTHS[d.getMonth()]}, ${hm}`;
}

const VIA = { prompt: "with a prompt", "session start": "as its session started", "end of turn": "at the end of a turn" };

/** The waiting request, for the commit pictogram's tip. No agent can be reached while idle, so it says it waits. */
export function waitingTip(project, ask) {
  const who = sessionName(ask?.agent, ask?.session);
  return who
    ? `Sent to ${who}, the last session in ${project}. It commits and pushes at its next turn; an idle agent cannot be reached, so it waits for your next prompt there. Click to withdraw.`
    : `Sent: the next agent turn in ${project} commits and pushes. Click to withdraw.`;
}

/** Who took the last request, when, and how; null without a receipt. */
export function takenLine(taken, now = new Date()) {
  if (!taken?.taken_at) return null;
  const who = sessionName(taken.agent, taken.session) || "The agent";
  const how = VIA[taken.via] ? ` ${VIA[taken.via]}` : "";
  const moved = taken.meant_for && taken.meant_for !== taken.session ? " (it started a turn there before the session the request named)" : "";
  return `${who} took the commit request at ${clock(taken.taken_at, now)}${how}${moved}.`;
}
