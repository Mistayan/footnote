// npm test
import { test } from "node:test";
import assert from "node:assert/strict";
import { clock, sessionName, takenLine, waitingTip } from "./asks.js";

const now = new Date(2026, 10, 23, 18, 30);
const at = (d) => Math.floor(d.getTime() / 1000);

test("a session is named by its agent and a short id", () => {
  assert.equal(sessionName("claude", "3f2a1b9c-77aa-4e0b"), "Claude Code session 3f2a1b9c");
  assert.equal(sessionName("codex", ""), "Codex");
  assert.equal(sessionName("", "abc"), "Agent session abc");
  assert.equal(sessionName("", "unknown"), null);
  assert.equal(sessionName(null, null), null);
});

test("the time is a clock today and a date before", () => {
  assert.equal(clock(at(new Date(2026, 10, 23, 14, 5)), now), "14:05");
  assert.equal(clock(at(new Date(2026, 10, 22, 9, 0)), now), "22 Nov, 09:00");
});

test("a waiting request names its session and says an idle agent waits", () => {
  const tip = waitingTip("shop-api", { agent: "claude", session: "3f2a1b9c99" });
  assert.match(tip, /Sent to Claude Code session 3f2a1b9c, the last session in shop-api/);
  assert.match(tip, /idle agent cannot be reached/);
  assert.match(waitingTip("shop-api", {}), /next agent turn in shop-api/);
});

test("a receipt says who took the request, when and how", () => {
  const taken = { agent: "codex", session: "s-123456789", meant_for: "s-123456789", via: "end of turn", taken_at: at(new Date(2026, 10, 23, 14, 5)) };
  assert.equal(takenLine(taken, now), "Codex session s-123456 took the commit request at 14:05 at the end of a turn.");
  assert.match(takenLine({ ...taken, meant_for: "other" }, now), /before the session the request named/);
  assert.equal(takenLine(null, now), null);
});
