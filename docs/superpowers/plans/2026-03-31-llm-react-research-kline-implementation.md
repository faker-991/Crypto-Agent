# LLM ReAct Research And Kline Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `ResearchAgent` and `KlineAgent` use the shared OpenAI-compatible model as their default ReAct engine while preserving bounded tool access and trace visibility.

**Architecture:** Introduce a reusable OpenAI-compatible ReAct client plus a safe heuristic fallback, then refactor `KlineAgent` onto the existing `ReActLoopService` and `ToolRuntime` pattern used by `ResearchAgent`. Keep `search_web` on the current `Exa -> DuckDuckGo fallback` path and preserve provider/strategy metadata in tool outputs.

**Tech Stack:** FastAPI, httpx, Pydantic, existing ReAct runtime, Binance market services, OpenAI-compatible chat completions.

---

## Chunk 1: Shared ReAct LLM Client

### Task 1: Add red tests for a reusable OpenAI-compatible ReAct client

**Files:**
- Create: `backend/tests/test_react_llm_service.py`
- Modify: `backend/app/services/react_llm_service.py`

- [ ] **Step 1: Write the failing test**

Cover:
- configured client reads `OPENAI_*`
- remote completion returns content plus usage/model/provider
- malformed or unavailable remote response can be surfaced to caller

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest backend/tests/test_react_llm_service.py -q`
Expected: FAIL because the service file does not exist yet.

- [ ] **Step 3: Write minimal implementation**

Create `backend/app/services/react_llm_service.py` with:
- `OpenAICompatibleReActLLMClient`
- env-file loading aligned with answer generation
- `.is_configured()`
- `.complete(messages=...)`

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest backend/tests/test_react_llm_service.py -q`
Expected: PASS

## Chunk 2: ResearchAgent Remote-First ReAct

### Task 2: Add red tests for remote-first research behavior

**Files:**
- Modify: `backend/tests/test_research_agent.py`
- Modify: `backend/app/agents/research_agent.py`

- [ ] **Step 1: Write the failing test**

Add tests that prove:
- when remote ReAct client is configured, `ResearchAgent` uses it
- when remote ReAct client fails, research falls back to heuristic behavior
- trace/terminal state preserves model provider metadata

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest backend/tests/test_research_agent.py -q`
Expected: FAIL on the new assertions.

- [ ] **Step 3: Write minimal implementation**

Update `ResearchAgent` to:
- construct remote client by default
- wrap it in a fallback composite with heuristic backup
- preserve existing bounded tool set

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest backend/tests/test_research_agent.py -q`
Expected: PASS

## Chunk 3: KlineAgent ReAct Runtime

### Task 3: Add red tests for an LLM-driven KlineAgent

**Files:**
- Modify: `backend/tests/test_kline_agent.py`
- Create: `backend/app/agents/kline_result_assembler.py`
- Create: `backend/app/agents/tools/kline_runtime_tools.py`
- Modify: `backend/app/agents/kline_agent.py`

- [ ] **Step 1: Write the failing test**

Cover:
- kline agent executes through `ReActLoopService`
- allowed tools are limited to `market + kline`
- agent may inspect multiple timeframes autonomously
- output still contains analyses, summary, tool_calls, and missing-information semantics

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest backend/tests/test_kline_agent.py -q`
Expected: FAIL because the agent is currently deterministic.

- [ ] **Step 3: Write minimal implementation**

Refactor `KlineAgent` to:
- build runtime tool specs/executors for kline tasks
- use shared remote-first ReAct client
- assemble final technical-analysis result via `KlineResultAssembler`

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest backend/tests/test_kline_agent.py -q`
Expected: PASS

## Chunk 4: Trace And Tool Summary Verification

### Task 4: Add red tests for model metadata and provider visibility

**Files:**
- Modify: `backend/tests/test_react_loop_service.py`
- Modify: `backend/tests/test_trace_log.py`
- Modify: `backend/tests/test_readable_trace_formatter.py`
- Modify: `backend/app/runtime/react_loop_service.py`
- Modify: `backend/app/services/readable_trace_formatter.py`

- [ ] **Step 1: Write the failing test**

Cover:
- llm spans on research and kline rounds show remote model metadata
- fallback path is visible in degraded/error attributes
- `search_web` provider remains visible in summaries

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest backend/tests/test_react_loop_service.py backend/tests/test_trace_log.py backend/tests/test_readable_trace_formatter.py -q`
Expected: FAIL on new expectations.

- [ ] **Step 3: Write minimal implementation**

Adjust trace finishing and readable summaries as needed so:
- model/provider are preserved
- fallback reason is visible
- search provider is visible in tool output summaries

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest backend/tests/test_react_loop_service.py backend/tests/test_trace_log.py backend/tests/test_readable_trace_formatter.py -q`
Expected: PASS

## Chunk 5: Focused Regression

### Task 5: Run targeted regression for the new agent paths

**Files:**
- Modify: none
- Test: `backend/tests/test_react_llm_service.py`
- Test: `backend/tests/test_research_tools.py`
- Test: `backend/tests/test_research_agent.py`
- Test: `backend/tests/test_kline_agent.py`
- Test: `backend/tests/test_react_loop_service.py`
- Test: `backend/tests/test_tool_runtime.py`
- Test: `backend/tests/test_trace_log.py`
- Test: `backend/tests/test_readable_trace_formatter.py`

- [ ] **Step 1: Run focused regression**

Run:
`pytest backend/tests/test_react_llm_service.py backend/tests/test_research_tools.py backend/tests/test_research_agent.py backend/tests/test_kline_agent.py backend/tests/test_react_loop_service.py backend/tests/test_tool_runtime.py backend/tests/test_trace_log.py backend/tests/test_readable_trace_formatter.py -q`

Expected: PASS

- [ ] **Step 2: Run one in-process smoke test**

Run a direct `ConversationService.send_message(...)` smoke query and confirm:
- answer generation uses the configured remote model
- research and kline traces now show agent-level llm spans as well

- [ ] **Step 3: Commit**

```bash
git add backend/app backend/tests docs/superpowers/specs/2026-03-31-llm-react-research-kline-design.md docs/superpowers/plans/2026-03-31-llm-react-research-kline-implementation.md
git commit -m "feat: add remote llm react runtime for research and kline agents"
```
