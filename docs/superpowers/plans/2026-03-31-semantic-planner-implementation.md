# Semantic Planner Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the planner use LLM semantic planning as the primary source for `asset / timeframes / market_type / response_style`, with heuristic extraction retained only as fallback and validation support.

**Architecture:** Keep the existing `Planner -> Executor` architecture, but insert a lightweight normalization layer between `PlannerLLMService` and `Planner`. `PlannerLLMService` becomes the primary semantic parser, `PlannerNormalizer` converts raw planner inputs into stable slots, and fallback extraction only runs when the LLM path is unavailable or invalid.

**Tech Stack:** FastAPI backend, existing planner/orchestrator runtime, Pydantic schemas, httpx-based OpenAI-compatible planner client, pytest.

---

## Chunk 1: Semantic Planner Inputs And Normalization

### Task 1: Add failing tests for semantic planner inputs and normalization

**Files:**
- Create: `backend/app/orchestrator/planner_normalizer.py`
- Modify: `backend/tests/test_planner_llm_service.py`
- Modify: `backend/tests/test_planner.py`

- [ ] **Step 1: Write the failing tests**

Cover:
- `PlannerLLMService` accepts `timeframes=["1h","4h"]`
- `PlannerLLMService` accepts semantic input fields like `analysis_intent` and `response_style`
- planner normalization preserves valid `1h/4h` order and drops unsupported intervals
- planner uses LLM-provided `timeframes` instead of overriding them with `_extract_timeframes()`

- [ ] **Step 2: Run tests to verify they fail**

Run:
`pytest backend/tests/test_planner_llm_service.py backend/tests/test_planner.py -q`

Expected:
- FAIL because there is no normalizer yet and planner still relies on heuristic extraction in plan construction

- [ ] **Step 3: Write minimal implementation**

Create `backend/app/orchestrator/planner_normalizer.py` with:
- `normalize_inputs(raw_inputs: dict | None, query: str, session_timeframes: list[str]) -> dict`
- timeframe allowlist:
  - `15m`
  - `30m`
  - `1h`
  - `4h`
  - `1d`
  - `1w`
- helpers:
  - dedupe while preserving order
  - normalize `market_type`
  - normalize `response_style`
  - normalize `analysis_intent`

Update `backend/app/orchestrator/planner.py` so:
- LLM decision inputs are normalized before plan construction
- LLM-provided `timeframes` win when valid
- fallback extraction only fills gaps when normalized `timeframes` are empty

- [ ] **Step 4: Run tests to verify they pass**

Run:
`pytest backend/tests/test_planner_llm_service.py backend/tests/test_planner.py -q`

Expected:
- PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/orchestrator/planner_normalizer.py backend/app/orchestrator/planner.py backend/tests/test_planner_llm_service.py backend/tests/test_planner.py
git commit -m "feat: normalize semantic planner inputs"
```

## Chunk 2: PlannerLLMService Prompt Upgrade

### Task 2: Add failing tests for semantic prompt expectations

**Files:**
- Modify: `backend/tests/test_planner_llm_service.py`
- Modify: `backend/app/services/planner_llm_service.py`

- [ ] **Step 1: Write the failing tests**

Cover:
- planner system prompt explicitly asks for:
  - `asset`
  - `timeframes`
  - `market_type`
  - `analysis_intent`
  - `response_style`
- planner service keeps returning `None` on invalid schema output
- planner timeout default is long enough for semantic parsing

- [ ] **Step 2: Run tests to verify they fail**

Run:
`pytest backend/tests/test_planner_llm_service.py -q`

Expected:
- FAIL because prompt and timeout defaults are still MVP-level

- [ ] **Step 3: Write minimal implementation**

Update `backend/app/services/planner_llm_service.py`:
- expand `_system_prompt()` so the model is instructed to:
  - extract natural-language timeframe expressions like `1h`, `小时线`, `周线`, `日线`
  - output normalized `inputs`
  - choose `response_style` and `analysis_intent`
- increase default timeout from `20.0` to `60.0`
- keep invalid outputs returning `None`

- [ ] **Step 4: Run tests to verify they pass**

Run:
`pytest backend/tests/test_planner_llm_service.py -q`

Expected:
- PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/planner_llm_service.py backend/tests/test_planner_llm_service.py
git commit -m "feat: upgrade planner semantic prompt"
```

## Chunk 3: Fallback Demotion And Timeframe Coverage

### Task 3: Add failing tests for fallback-only timeframe extraction

**Files:**
- Modify: `backend/tests/test_planner.py`
- Modify: `backend/app/orchestrator/planner.py`

- [ ] **Step 1: Write the failing tests**

Cover:
- fallback extraction supports:
  - `1h`
  - `小时线`
  - `15m`
  - `30m`
- fallback only runs when:
  - LLM is unavailable
  - LLM returns invalid output
  - normalized LLM `timeframes` are empty
- plan preserves `response_style` in `planner_inputs`

- [ ] **Step 2: Run tests to verify they fail**

Run:
`pytest backend/tests/test_planner.py -q`

Expected:
- FAIL because fallback extraction is still too narrow and planner drops semantic style fields

- [ ] **Step 3: Write minimal implementation**

Update `backend/app/orchestrator/planner.py`:
- broaden `_extract_timeframes()` to cover:
  - `1h`
  - `小时线`
  - `15m`
  - `30m`
- add explicit planner fallback reason handling:
  - `not_configured`
  - `llm_returned_none`
  - `missing_timeframes_after_normalization`
- carry `response_style` and `analysis_intent` through `planner_inputs`

- [ ] **Step 4: Run tests to verify they pass**

Run:
`pytest backend/tests/test_planner.py -q`

Expected:
- PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/orchestrator/planner.py backend/tests/test_planner.py
git commit -m "feat: demote planner fallback to backup parsing"
```

## Chunk 4: Orchestrator And Trace Visibility

### Task 4: Add failing tests for planner source and fallback reason visibility

**Files:**
- Modify: `backend/tests/test_orchestrator_service.py`
- Modify: `backend/tests/test_trace_log.py`
- Modify: `backend/tests/test_trace_api.py`
- Modify: `backend/app/orchestrator/orchestrator_service.py`
- Modify: `backend/app/services/trace_log_service.py`

- [ ] **Step 1: Write the failing tests**

Cover:
- orchestrator execution summary includes:
  - `planner_source`
  - `planner_fallback_reason`
  - normalized `timeframes`
  - `response_style`
- trace payload includes fallback reason when planner did not use semantic LLM output

- [ ] **Step 2: Run tests to verify they fail**

Run:
`pytest backend/tests/test_orchestrator_service.py backend/tests/test_trace_log.py backend/tests/test_trace_api.py -q`

Expected:
- FAIL because fallback reason is not yet surfaced consistently

- [ ] **Step 3: Write minimal implementation**

Update:
- `backend/app/orchestrator/orchestrator_service.py`
  - include normalized planner metadata in `execution_summary`
- `backend/app/services/trace_log_service.py`
  - persist planner fallback reason in planner span attributes or execution summary derived payload

- [ ] **Step 4: Run tests to verify they pass**

Run:
`pytest backend/tests/test_orchestrator_service.py backend/tests/test_trace_log.py backend/tests/test_trace_api.py -q`

Expected:
- PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/orchestrator/orchestrator_service.py backend/app/services/trace_log_service.py backend/tests/test_orchestrator_service.py backend/tests/test_trace_log.py backend/tests/test_trace_api.py
git commit -m "feat: expose semantic planner trace metadata"
```

## Chunk 5: Focused Regression And Smoke Coverage

### Task 5: Run targeted regression and semantic planner smoke cases

**Files:**
- Modify: none
- Test: `backend/tests/test_planner_llm_service.py`
- Test: `backend/tests/test_planner.py`
- Test: `backend/tests/test_orchestrator_service.py`
- Test: `backend/tests/test_trace_log.py`
- Test: `backend/tests/test_trace_api.py`
- Test: `backend/tests/test_conversation_api.py`

- [ ] **Step 1: Run focused regression**

Run:
`pytest backend/tests/test_planner_llm_service.py backend/tests/test_planner.py backend/tests/test_orchestrator_service.py backend/tests/test_trace_log.py backend/tests/test_trace_api.py backend/tests/test_conversation_api.py -q`

Expected:
- PASS

- [ ] **Step 2: Run one in-process semantic smoke test**

Run a direct planner/orchestrator smoke with:
- `帮我看下 BTC 现货的1h线、4h线，然后给出投资建议`

Verify:
- planner chooses `kline_only`
- `timeframes == ["1h", "4h"]`
- `planner_source == "llm"` when remote planner succeeds
- fallback reason is empty on success, populated on fallback

- [ ] **Step 3: Commit**

```bash
git add backend/tests
git commit -m "test: cover semantic planner timeframes and metadata"
```
