# MCP compact results (#511)

Measured 2026-11-22 on a copy of a real agent memory database (156 memories), query `MCP round trips footnote_get`,
bytes of the tool result text. "Before" is `verbose: true`, which returns the fields the old default returned.

| Call | Before | After | Change |
|---|---:|---:|---:|
| `footnote_recall`, hybrid, 8 hits (`--features llama`) | 5,272 | 3,810 | −27.7% |
| `footnote_recall`, lexical, 8 hits | 4,260 | 3,370 | −20.9% |
| `footnote_get`, 1 id | 791 | 562 | −28.9% |
| `footnote_get`, 3 ids | 3 calls, about 2,370 | 1 call, 1,389 | −41%, 2 fewer round trips |

What the compact form drops: `sha256`, `revision`, `extractor`, `status`, `page: null`, `line`, `memory:<hash>` paths,
fusion and cosine scores, and the per-hit trust label (stated once per response instead). Document hits keep their
path or URL, line and heading so they can still be cited, and say `stale` when the file changed since indexing.

Lexical gains less because its hits carry no scores; what remains is the text itself.
