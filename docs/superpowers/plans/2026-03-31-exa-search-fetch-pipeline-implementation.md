# Exa Search And Fetch Pipeline Implementation Plan

## Chunk 1: Research Search Upgrade

- add Exa HTTP search client logic behind `ResearchToolbox.search_web`
- keep DuckDuckGo as fallback
- normalize provider metadata in the response payload
- add tests for Exa success and fallback behavior

## Chunk 2: Fetch Pipeline

- replace direct `fetch_page` logic with a small staged pipeline
- implement `simple_http` and `readability_like` stages
- add attempt metadata and final strategy fields
- add tests for first-stage success, staged fallback, and structured failure

## Chunk 3: Trace Readability

- surface fetch strategy and fallback count in normalized tool summaries
- update readable trace formatting if needed so tool details show attempts cleanly
- add formatter coverage if output shape changes

## Chunk 4: Verification

- run focused backend tests for research tools, research agent, and readable trace
- confirm no regressions in tool runtime contracts
