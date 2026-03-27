# Agentic Planner Runtime Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the current rule-style planner/runtime with an LLM planner that chooses execution paths, drives tool-backed `ResearchAgent` and `KlineAgent`, and always routes final user answers through `SummaryAgent`.

**Architecture:** Keep the existing planner/orchestrator shell, but replace the current deterministic `Planner` with an LLM-backed planner contract, convert `ResearchAgent` and `KlineAgent` into bounded tool-loop agents, then wire `OrchestratorService`, conversations, and traces to record the full planning and execution path. Deliver in vertical slices so the app remains runnable after each checkpoint.

**Tech Stack:** FastAPI, Pydantic, pytest, httpx, local JSON/Markdown memory files, Binance public market endpoints, local indicator computation

---

## Planning Notes

- Current workspace is not a git repository. Treat commit steps as local checkpoints only.
- Keep the first implementation bounded to:
  - `clarify`
  - `kline_only`
  - `research_only`
  - `mixed_analysis`
- Each sub-agent is limited to `3` rounds of `tool call -> reflection -> optional next call`.
- Evidence insufficiency is a first-class result, not an error fallback.
- Prefer free/no-key integrations for phase 1:
  - Binance public endpoints
  - public web search + page fetch
  - local indicator calculation

## File Structure

### New backend files

- Create: `backend/app/agents/tools/__init__.py`
- Create: `backend/app/agents/tools/research_tools.py`
- Create: `backend/app/agents/tools/kline_tools.py`
- Create: `backend/app/services/planner_llm_service.py`
- Create: `backend/app/schemas/agentic_plan.py`
- Create: `backend/app/schemas/agentic_result.py`
- Create: `backend/tests/test_planner_llm_service.py`
- Create: `backend/tests/test_research_tools.py`
- Create: `backend/tests/test_kline_tools.py`

### Existing backend files to modify

- Modify: `backend/app/orchestrator/planner.py`
- Modify: `backend/app/orchestrator/executor.py`
- Modify: `backend/app/orchestrator/orchestrator_service.py`
- Modify: `backend/app/agents/research_agent.py`
- Modify: `backend/app/agents/kline_agent.py`
- Modify: `backend/app/agents/summary_agent.py`
- Modify: `backend/app/services/answer_generation_service.py`
- Modify: `backend/app/services/trace_log_service.py`
- Modify: `backend/app/services/external_research_service.py`
- Modify: `backend/app/services/kline_analysis_service.py`
- Modify: `backend/tests/test_planner.py`
- Modify: `backend/tests/test_executor.py`
- Modify: `backend/tests/test_summary_agent.py`
- Modify: `backend/tests/test_orchestrator_service.py`
- Modify: `backend/tests/test_conversation_api.py`
- Modify: `backend/tests/test_trace_log.py`
- Modify: `backend/tests/test_trace_api.py`

### Existing frontend files to modify later in the slice

- Modify: `frontend/lib/api.ts`
- Modify: `frontend/components/conversation-panel.tsx`
- Modify: `frontend/app/traces/page.tsx`

## Chunk 1: Planner Contract and LLM Decision Layer

### Task 1: Add agentic planner/result schemas

**Files:**
- Create: `backend/app/schemas/agentic_plan.py`
- Create: `backend/app/schemas/agentic_result.py`
- Test: `backend/tests/test_planner.py`

- [ ] **Step 1: Write failing tests for the new planner contract**

Cover:
- planner modes `clarify`, `research_only`, `kline_only`, `mixed_analysis`
- planner outputs `reasoning_summary`, `agents_to_invoke`, and normalized inputs
- agent result supports `status`, `evidence_sufficient`, `tool_calls`, `rounds_used`

- [ ] **Step 2: Run the planner tests to verify failure**

Run: `cd /home/akalaopaoer/code/crypto-agent/backend && pytest tests/test_planner.py -v`
Expected: FAIL because the agentic planner schema does not exist yet

- [ ] **Step 3: Implement the minimal schemas**

Define focused Pydantic models for:
- planner mode and plan payload
- sub-agent result payload
- tool call record

- [ ] **Step 4: Re-run planner tests**

Run: `cd /home/akalaopaoer/code/crypto-agent/backend && pytest tests/test_planner.py -v`
Expected: PASS for schema-level expectations

### Task 2: Add `PlannerLLMService`

**Files:**
- Create: `backend/app/services/planner_llm_service.py`
- Modify: `backend/app/orchestrator/planner.py`
- Test: `backend/tests/test_planner_llm_service.py`
- Test: `backend/tests/test_planner.py`

- [ ] **Step 1: Write failing tests for LLM planner behavior**

Cover:
- planner uses LLM output when available
- planner falls back to deterministic safe behavior if LLM fails
- follow-up queries can still resolve through session context
- planner cannot emit unsupported modes

- [ ] **Step 2: Run the planner LLM tests to verify failure**

Run: `cd /home/akalaopaoer/code/crypto-agent/backend && pytest tests/test_planner_llm_service.py tests/test_planner.py -v`
Expected: FAIL because `PlannerLLMService` is missing

- [ ] **Step 3: Implement `PlannerLLMService` and integrate it into `Planner`**

Implementation notes:
- Use OpenAI-compatible chat completion just like answer generation
- Require structured JSON output
- Validate and clamp mode/agents to supported values
- Keep a deterministic fallback for safety

- [ ] **Step 4: Re-run planner LLM tests**

Run: `cd /home/akalaopaoer/code/crypto-agent/backend && pytest tests/test_planner_llm_service.py tests/test_planner.py -v`
Expected: PASS

## Chunk 2: Tool-Backed Kline Agent

### Task 3: Add concrete kline tools

**Files:**
- Create: `backend/app/agents/tools/kline_tools.py`
- Modify: `backend/app/services/kline_analysis_service.py`
- Test: `backend/tests/test_kline_tools.py`

- [ ] **Step 1: Write failing tests for kline tools**

Cover:
- `get_klines` returns normalized candle payloads
- `get_ticker` returns current market snapshot when available
- `compute_indicators` returns RSI, MACD, EMA/SMA, Bollinger Bands, ATR
- indicator computation returns explicit insufficiency when candle data is too short

- [ ] **Step 2: Run the kline tool tests to verify failure**

Run: `cd /home/akalaopaoer/code/crypto-agent/backend && pytest tests/test_kline_tools.py -v`
Expected: FAIL because the tool module does not exist yet

- [ ] **Step 3: Implement the kline tool module**

Implementation notes:
- Reuse existing Binance market data code for candle and ticker fetches
- Prefer local Python indicator math
- Keep tool outputs serializable for trace persistence

- [ ] **Step 4: Re-run kline tool tests**

Run: `cd /home/akalaopaoer/code/crypto-agent/backend && pytest tests/test_kline_tools.py -v`
Expected: PASS

### Task 4: Convert `KlineAgent` into a bounded tool-loop agent

**Files:**
- Modify: `backend/app/agents/kline_agent.py`
- Modify: `backend/app/orchestrator/executor.py`
- Modify: `backend/tests/test_kline_agent.py`
- Modify: `backend/tests/test_executor.py`

- [ ] **Step 1: Write failing tests for tool-loop execution**

Cover:
- `KlineAgent` records tool calls and rounds used
- agent stops early when evidence is sufficient
- agent returns `insufficient` when data is unavailable
- executor consumes the new structured agent result

- [ ] **Step 2: Run the tests to verify failure**

Run: `cd /home/akalaopaoer/code/crypto-agent/backend && pytest tests/test_kline_agent.py tests/test_executor.py -v`
Expected: FAIL because `KlineAgent` still returns the old payload shape

- [ ] **Step 3: Implement the bounded kline loop**

Implementation notes:
- Max `3` rounds
- Round 1: fetch kline + ticker
- Round 2: compute indicators
- Round 3: optionally add a missing timeframe or stop
- Return `evidence_sufficient=False` if the agent cannot build a trustworthy technical view

- [ ] **Step 4: Re-run the tests**

Run: `cd /home/akalaopaoer/code/crypto-agent/backend && pytest tests/test_kline_agent.py tests/test_executor.py -v`
Expected: PASS

## Chunk 3: Tool-Backed Research Agent

### Task 5: Add concrete research tools

**Files:**
- Create: `backend/app/agents/tools/research_tools.py`
- Modify: `backend/app/services/external_research_service.py`
- Test: `backend/tests/test_research_tools.py`

- [ ] **Step 1: Write failing tests for research tools**

Cover:
- public web search returns candidate source metadata
- page fetch returns normalized title/text output
- market/protocol snapshot helpers still work as tool inputs
- page fetch returns explicit failure payload instead of raising when source is unavailable

- [ ] **Step 2: Run the research tool tests to verify failure**

Run: `cd /home/akalaopaoer/code/crypto-agent/backend && pytest tests/test_research_tools.py -v`
Expected: FAIL because the tool module does not exist yet

- [ ] **Step 3: Implement the research tool module**

Implementation notes:
- Use public-search-compatible HTTP fetches for phase 1
- Normalize source metadata for trace storage
- Do not hardcode Tavily or any paid API as a requirement

- [ ] **Step 4: Re-run research tool tests**

Run: `cd /home/akalaopaoer/code/crypto-agent/backend && pytest tests/test_research_tools.py -v`
Expected: PASS

### Task 6: Convert `ResearchAgent` into a bounded tool-loop agent

**Files:**
- Modify: `backend/app/agents/research_agent.py`
- Modify: `backend/app/orchestrator/executor.py`
- Modify: `backend/tests/test_executor.py`
- Modify: `backend/tests/test_orchestrator_service.py`

- [ ] **Step 1: Write failing tests for research loop behavior**

Cover:
- research agent performs search/fetch rounds
- research agent captures evidence categories and missing gaps
- research agent stops with `insufficient` when enough evidence cannot be found
- mixed execution still preserves both research and kline outputs

- [ ] **Step 2: Run the tests to verify failure**

Run: `cd /home/akalaopaoer/code/crypto-agent/backend && pytest tests/test_executor.py tests/test_orchestrator_service.py -v`
Expected: FAIL because `ResearchAgent` still returns a static template result

- [ ] **Step 3: Implement the bounded research loop**

Implementation notes:
- Max `3` rounds
- Up to `4` search queries
- Up to `10` fetched pages
- Explicitly track missing evidence buckets
- Return `insufficient` when market/protocol/risk/catalyst coverage remains weak

- [ ] **Step 4: Re-run the tests**

Run: `cd /home/akalaopaoer/code/crypto-agent/backend && pytest tests/test_executor.py tests/test_orchestrator_service.py -v`
Expected: PASS

## Chunk 4: Unified Summary and Orchestrator Path

### Task 7: Force all paths through `SummaryAgent`

**Files:**
- Modify: `backend/app/agents/summary_agent.py`
- Modify: `backend/app/orchestrator/orchestrator_service.py`
- Modify: `backend/tests/test_summary_agent.py`
- Modify: `backend/tests/test_orchestrator_service.py`

- [ ] **Step 1: Write failing tests for unified summary behavior**

Cover:
- `kline_only` still ends in `SummaryAgent`
- `research_only` still ends in `SummaryAgent`
- `mixed_analysis` merges both agent outputs
- if an upstream result is `insufficient`, summary preserves that limitation explicitly

- [ ] **Step 2: Run the tests to verify failure**

Run: `cd /home/akalaopaoer/code/crypto-agent/backend && pytest tests/test_summary_agent.py tests/test_orchestrator_service.py -v`
Expected: FAIL because single-path execution still short-circuits around summary

- [ ] **Step 3: Implement the unified summary path**

Implementation notes:
- `SummaryAgent` becomes the only producer of `final_answer`
- upstream agent payloads stay structured
- `execution_summary` should include:
  - planner mode
  - invoked agents
  - evidence sufficiency by agent
  - final summary text

- [ ] **Step 4: Re-run the tests**

Run: `cd /home/akalaopaoer/code/crypto-agent/backend && pytest tests/test_summary_agent.py tests/test_orchestrator_service.py -v`
Expected: PASS

### Task 8: Expand trace semantics for planner and agent loops

**Files:**
- Modify: `backend/app/services/trace_log_service.py`
- Modify: `backend/tests/test_trace_log.py`
- Modify: `backend/tests/test_trace_api.py`

- [ ] **Step 1: Write failing trace tests**

Cover:
- planner mode and reasoning are persisted
- per-agent rounds and tool calls are persisted
- evidence sufficiency is visible in trace payloads
- trace list/read APIs still work with the richer payload

- [ ] **Step 2: Run the tests to verify failure**

Run: `cd /home/akalaopaoer/code/crypto-agent/backend && pytest tests/test_trace_log.py tests/test_trace_api.py -v`
Expected: FAIL because existing trace payload does not include planner/agent loop detail

- [ ] **Step 3: Implement expanded trace payloads**

Implementation notes:
- Keep legacy trace reading compatibility where practical
- Write planner events, tool call events, reflection events, and summary events
- Avoid storing full raw page bodies if that makes traces too large; prefer summaries

- [ ] **Step 4: Re-run the trace tests**

Run: `cd /home/akalaopaoer/code/crypto-agent/backend && pytest tests/test_trace_log.py tests/test_trace_api.py -v`
Expected: PASS

## Chunk 5: Conversation and UI Integration

### Task 9: Use agentic summary output in conversations

**Files:**
- Modify: `backend/app/services/answer_generation_service.py`
- Modify: `backend/app/services/conversation_service.py`
- Modify: `backend/tests/test_conversation_api.py`

- [ ] **Step 1: Write failing conversation tests**

Cover:
- conversation assistant reply is derived from unified summary output
- answer generation sees planner mode and per-agent sufficiency in its prompt context
- evidence insufficiency reaches the user instead of being smoothed over

- [ ] **Step 2: Run the tests to verify failure**

Run: `cd /home/akalaopaoer/code/crypto-agent/backend && pytest tests/test_conversation_api.py -v`
Expected: FAIL because conversation replies still rely on the older execution summary shape

- [ ] **Step 3: Implement conversation and answer-generation integration**

Implementation notes:
- Keep the OpenAI-compatible answer generator
- Use the structured summary payload as primary prompt context
- Preserve a deterministic fallback path when the LLM is unavailable

- [ ] **Step 4: Re-run the tests**

Run: `cd /home/akalaopaoer/code/crypto-agent/backend && pytest tests/test_conversation_api.py -v`
Expected: PASS

### Task 10: Surface planner/agent traces in the frontend

**Files:**
- Modify: `frontend/lib/api.ts`
- Modify: `frontend/components/conversation-panel.tsx`
- Modify: `frontend/app/traces/page.tsx`

- [ ] **Step 1: Add failing type or render assertions as appropriate**

If no frontend test harness exists, encode the expected data shape through TypeScript types first.

- [ ] **Step 2: Run frontend verification to expose the failure**

Run: `cd /home/akalaopaoer/code/crypto-agent/frontend && npx tsc --noEmit`
Expected: FAIL after backend shape changes until frontend types are updated

- [ ] **Step 3: Update frontend types and planner trace rendering**

Implementation notes:
- Display planner mode
- Display executed agents
- Display sufficiency/inadequacy state
- Keep layout changes minimal for this slice

- [ ] **Step 4: Re-run frontend verification**

Run:
- `cd /home/akalaopaoer/code/crypto-agent/frontend && npm run lint`
- `cd /home/akalaopaoer/code/crypto-agent/frontend && npx tsc --noEmit`
- `cd /home/akalaopaoer/code/crypto-agent/frontend && npm run build`

Expected: PASS

## Final Verification

- [ ] Run targeted backend suites:

```bash
cd /home/akalaopaoer/code/crypto-agent/backend && pytest \
  tests/test_planner_llm_service.py \
  tests/test_planner.py \
  tests/test_research_tools.py \
  tests/test_kline_tools.py \
  tests/test_kline_agent.py \
  tests/test_executor.py \
  tests/test_summary_agent.py \
  tests/test_orchestrator_service.py \
  tests/test_trace_log.py \
  tests/test_trace_api.py \
  tests/test_conversation_api.py -v
```

- [ ] Run frontend verification:

```bash
cd /home/akalaopaoer/code/crypto-agent/frontend && npm run lint
cd /home/akalaopaoer/code/crypto-agent/frontend && npx tsc --noEmit
cd /home/akalaopaoer/code/crypto-agent/frontend && npm run build
```

- [ ] Manual smoke:
  - start backend and frontend
  - ask a kline-only question
  - ask a research-only question
  - ask a mixed question
  - confirm trace shows planner mode, agent rounds, tool calls, and summary outcome

