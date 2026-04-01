# LLM ReAct Research And Kline Design

## Goal

Make both `ResearchAgent` and `KlineAgent` behave like real tool-augmented agents by:

- using the existing OpenAI-compatible model configuration as the default ReAct decision engine
- keeping tool access bounded by domain
- preserving the current trace contract
- keeping `search_web` practically usable via `Exa -> DuckDuckGo fallback`

This closes the gap where only answer generation uses a real LLM while the named agents still behave like deterministic workers or heuristic stubs.

## Scope

In scope:

- default external LLM client for `ResearchAgent`
- default external LLM client for `KlineAgent`
- Kline-side ReAct execution with bounded market and kline tools
- heuristic fallback when remote LLM is unavailable or malformed
- trace visibility for remote-vs-heuristic execution
- web search provider provenance preserved in results and traces

Out of scope:

- planner changes beyond existing behavior
- browser automation / Playwright fallback
- full MCP transport discovery
- trade execution or write-capable tools

## Current State

### ResearchAgent

`ResearchAgent` already uses `ReActLoopService`, but defaults to `HeuristicResearchLLMClient`. That means it has a loop shape but not a real model-driven tool-choice policy by default.

### KlineAgent

`KlineAgent` is not agentic today. It deterministically fetches klines, computes indicators, and produces rule-based conclusions. It has no LLM-driven round loop, no autonomous tool-choice, and no bounded decision runtime.

### Search

`search_web` now supports:

- Exa when `EXA_API_KEY` is configured
- DuckDuckGo fallback otherwise

`fetch_page` is already a staged pipeline, so this design leaves that work in place.

## Target Architecture

### Shared LLM Client Pattern

Add an OpenAI-compatible ReAct client that:

- reads the same `OPENAI_*` / `ROUTER_LLM_*` / env-file configuration as answer generation
- exposes a completion interface compatible with `ReActLoopService`
- returns structured JSON actions
- records `model`, `provider`, and usage for traces

Both `ResearchAgent` and `KlineAgent` should default to:

1. remote OpenAI-compatible client
2. heuristic fallback client when remote is unavailable

### ResearchAgent

`ResearchAgent` keeps using `ReActLoopService`, but the default `llm_client` changes from heuristic-only to a composite client:

- remote first
- heuristic fallback second

Allowed tools remain bounded to `research + market`, which preserves the original safety envelope while making the agent truly model-driven.

### KlineAgent

Refactor `KlineAgent` onto the same runtime pattern:

- `ToolRuntime`
- `TraceRuntime`
- `ReActLoopService`
- a `KlineResultAssembler`

Allowed tools are bounded to `market + kline`.

Suggested tools:

- `get_klines`
- `get_ticker`
- `compute_indicators`

The agent may autonomously decide:

- which timeframe to inspect first
- whether to fetch ticker context
- whether a timeframe needs indicator calculation
- whether more timeframe evidence is needed before terminating

The agent may not:

- change the asset
- call non-market research tools
- call write-capable or unrelated tools

## Data Flow

### Research Path

`Planner -> Executor -> ResearchAgent -> ReActLoopService -> ToolRuntime -> research/market tools -> ResearchResultAssembler -> Summary/Answer`

### Kline Path

`Planner -> Executor -> KlineAgent -> ReActLoopService -> ToolRuntime -> kline/market tools -> KlineResultAssembler -> Summary/Answer`

## Trace Requirements

Trace must make it obvious whether the agent is actually LLM-driven.

Each agent run should show:

- `llm` span per round with remote model attributes when remote succeeds
- degraded or fallback markers when remote fails and heuristic takes over
- tool spans for each chosen action
- token usage when remote LLM was used

For search:

- `search_web` output should continue carrying `provider`
- trace summaries should surface the provider in tool output summaries

## Error Handling

### Remote LLM failure

If the remote model:

- times out
- returns non-JSON
- returns malformed step payloads

the system should:

- mark the relevant llm span as failed or degraded
- switch to heuristic fallback for that agent run
- continue execution if fallback can proceed safely

### Tool failure

Existing `ReActLoopService` guardrails stay in place:

- max rounds
- repeated identical call detection
- tool failure limit
- no-progress limit

## Files

Primary files:

- `backend/app/agents/research_agent.py`
- `backend/app/agents/kline_agent.py`
- `backend/app/runtime/react_loop_service.py`
- `backend/app/agents/tools/research_tools.py`

Likely new files:

- `backend/app/services/react_llm_service.py`
- `backend/app/agents/kline_result_assembler.py`
- `backend/app/agents/tools/kline_runtime_tools.py`

Likely test files:

- `backend/tests/test_research_agent.py`
- `backend/tests/test_kline_agent.py`
- `backend/tests/test_react_loop_service.py`

## Verification

Minimum verification for this slice:

- `ResearchAgent` uses remote LLM when configured
- `ResearchAgent` falls back to heuristic on remote failure
- `KlineAgent` runs through ReAct with bounded tools
- trace shows remote model metadata on agent llm spans
- search results still expose provider provenance

