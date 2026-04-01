# Exa Search And Fetch Pipeline Design

## Goal

Upgrade the `research` tool domain so that:

- `search_web` uses Exa as the primary search provider.
- `search_web` falls back to DuckDuckGo when Exa is unavailable.
- `fetch_page` becomes a resilient URL extraction pipeline instead of a single `GET`.
- trace output shows which fetch strategy succeeded or failed.

The public tool contract must remain stable for `ResearchAgent`, `ToolRuntime`, and the frontend trace views.

## Scope

In scope:

- Add an Exa-backed search client behind `ResearchToolbox.search_web`.
- Add a staged fetch pipeline behind `ResearchToolbox.fetch_page`.
- Preserve existing tool names and normalized return payloads.
- Surface fetch attempt metadata in tool outputs and trace summaries.
- Add focused backend coverage.

Out of scope for this slice:

- Full remote MCP transport integration for Exa.
- Browser automation inside the first implementation pass.
- Site-specific extractors beyond generic hooks and metadata.
- Replay or re-execution features.

## Design

### Search

`ResearchToolbox.search_web` should:

1. Try Exa search when `EXA_API_KEY` is configured.
2. Normalize Exa hits into the existing `title/url/snippet` shape.
3. Fall back to DuckDuckGo HTML search if Exa is unavailable or returns an error.
4. Report the chosen provider in the output payload so traces can show source provenance.

### Fetch

`ResearchToolbox.fetch_page` should delegate to a `PageFetchPipeline` with ordered stages:

1. `simple_http`
2. `readability_like`
3. future hooks such as `playwright_mcp` and domain-specific extractors

Each stage returns a normalized attempt record with:

- `strategy`
- `status`
- `duration_ms`
- `http_status`
- `content_bytes`
- `text_length`
- `failure_reason`
- `title`

The pipeline should stop on the first stage that produces sufficiently useful content.

### Success Criteria

A fetch stage only counts as successful when:

- it retrieves HTML successfully, and
- it extracts meaningful text beyond a low threshold, and
- the result is not obviously an error, login, or empty shell page

`HTTP 200` alone is not sufficient.

### Trace Contract

`fetch_page` tool output should include:

- `strategy`
- `attempts`
- `fallback_count`

The normalized tool executor summary should expose:

- final strategy
- fallback count
- title
- text preview

This lets the trace timeline show where the fetch succeeded and how many fallbacks were needed.

## Files

Primary files:

- `backend/app/agents/tools/research_tools.py`
- `backend/tests/test_research_tools.py`

Likely touch points:

- `backend/app/services/readable_trace_formatter.py`
- `backend/tests/test_readable_trace_formatter.py`

## Verification

Focused verification should cover:

- Exa success path
- Exa failure with DuckDuckGo fallback
- fetch success at first stage
- fetch fallback from basic extraction to readability-like extraction
- fetch failure with structured attempt reasons

