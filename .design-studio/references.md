# References (captured 2026-11-14, 1920×1080)

| Site | Take | Product shown working |
|---|---|---|
| zed.dev | Warm off-white ground, serif title with mono italic lede, the real product filling the hero, hairline frames instead of cards. | Yes: agent thread, inline diff, review comment, all live UI. |
| raycast.com | Near-black ground, one saturated red light form, very short headline, download as the only action. | No: a shader sculpture stands in for the product. |
| warp.dev | Monospace display type, a captioned live figure ("fig. 1 — the factory") with a legend and running counts, grid paper. | Yes, abstractly: a live grid of agents' tasks changing state. |
| mem0.ai | Category baseline to differ from: centred SaaS hero, purple accent, quick-start code block, YC badge. | Partly: an SDK code sample, no result. |

Footnote's own constraint (DESIGN.md, draft): no violet or blue-to-purple, proof red reserved for sources and Footnote's own results, real superscript footnotes, local-first (no external font requests in the final build).

Product content every mock shows in its first screen:
- an agent question and Footnote's cited answer: path, heading, line, revision, SHA-256 prefix, freshness (current / stale);
- a remembered preference coming back at session start;
- the proof: +42 % nDCG@10 against mem0 on mixed French/English, best on all five corpora, 4 to 10× faster queries than mem0.
