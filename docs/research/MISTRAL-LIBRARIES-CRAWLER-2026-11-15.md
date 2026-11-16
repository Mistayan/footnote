# Mistral Libraries: website indexing

Checked against Mistral's public documentation on 15 November 2026. This note
describes documented behavior, not an inspection of Mistral's hosted backend.

## What is documented

- [Vibe Work Libraries](https://docs.mistral.ai/vibe/work/libraries) persist
  across sessions and search attached documents with linked source references.
  In Vibe Work's `Webpage` flow, users provide URLs and only each supplied
  page's text is indexed; its child pages, images and charts are not included.
- [Mistral Studio Libraries](https://docs.mistral.ai/studio/search/libraries)
  has a separate `Index a website` workflow. A focused crawler follows child
  links from a seed URL. Options include 1–10,000 pages, depth 1–10,
  include/exclude URL rules, a refresh schedule and optional headless-browser
  rendering for JavaScript. Browser fetching is disabled by default. Indexing
  extracts text; the page says images and charts are not indexed in this flow.
  Studio document processing is pay-as-you-go.
- The Studio documentation says Libraries can be shared with Vibe and used by
  its agents, subject to the documented access rules. It also documents
  `connector_tokens` in the agent response's usage object, a potentially
  relevant source for the separate token-accounting idea.
- [Mistral's crawler documentation](https://docs.mistral.ai/robots)
  distinguishes `MistralAI-User` for user-directed page visits from
  `MistralAI-Index` for automated web search indexing. The documentation does
  not establish that either is the specific engine behind Studio Libraries.

## What is not established

The sources above do not identify the Studio crawler's library, source code,
browser engine, extraction algorithms, ranking stack or exact robots and rate
limit policy. The [Mistral Vibe CLI repository](https://github.com/mistralai/mistral-vibe)
is open source, but that fact does not establish that the hosted Libraries
crawler is included in it. No Mistral crawler was run or benchmarked here.

## Implications for Footnote

The supported product ideas are bounded site discovery, explicit URL scope,
optional JavaScript only when needed, per-source refresh and verifiable
citations. Footnote's minimal crawler already has page budgets, URL exclusions,
robots checks and source mapping; configurable depth, scheduled refresh and
browser rendering require separate design and evaluation. A comparison with
Mistral's actual quality requires a permitted, matched benchmark and cannot be
inferred from a feature list. Keep local/offline operation and the user's data
boundaries explicit when considering a hosted option.
