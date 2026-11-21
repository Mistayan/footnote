// Splits a Claude Code session file's token usage at the Footnote skill edit request (#456): the task's calls before it, and
// the calls the request caused. Usage: node split.mjs <session.jsonl>
import { readFileSync } from 'node:fs';

const lines = readFileSync(process.argv[2], 'utf8').split('\n').filter(Boolean).map((l) => JSON.parse(l));
const zero = () => ({ calls: 0, input: 0, cache_read: 0, cache_write: 0, output: 0, max_context: 0 });
const parts = { task: zero(), request: zero() };
let phase = 'task';
const seen = new Set();
for (const l of lines) {
  // The request is the Stop hook's reason, fed back as a non-assistant line; its opening words are unique to it.
  if (phase === 'task' && l.type !== 'assistant' && l.attachment?.type !== 'prompt_snapshot'
    && JSON.stringify(l).includes('Footnote: you read the skill \\"')) phase = 'request';
  const u = l.type === 'assistant' && l.message?.usage;
  if (!u) continue;
  // One API call can be split over several lines (one per content block): count it once, by message id.
  if (seen.has(l.message.id)) continue;
  seen.add(l.message.id);
  const p = parts[phase];
  p.calls += 1;
  p.input += u.input_tokens ?? 0;
  p.cache_read += u.cache_read_input_tokens ?? 0;
  p.cache_write += u.cache_creation_input_tokens ?? 0;
  p.output += u.output_tokens ?? 0;
  p.max_context = Math.max(p.max_context, (u.input_tokens ?? 0) + (u.cache_read_input_tokens ?? 0) + (u.cache_creation_input_tokens ?? 0));
}
console.log(JSON.stringify(parts, null, 1));
