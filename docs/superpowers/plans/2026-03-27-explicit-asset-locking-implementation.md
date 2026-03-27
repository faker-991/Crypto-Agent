# Explicit Asset Locking Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ensure a user’s explicitly mentioned asset, such as BTC, always overrides stale session context and cannot silently turn into another asset like ETH during planning or answer generation.

**Architecture:** Keep the existing planner-executor-answer pipeline, but add an explicit-asset lock in the planner and a downstream consistency guard in orchestration. The planner should prefer the asset extracted from the current message over session state or LLM-decided inputs, and orchestration should reject or correct mismatched execution summaries before answer generation.

**Tech Stack:** Python, FastAPI service layer, Pydantic schemas, pytest

---

## Chunk 1: Planner Asset Priority

### Task 1: Lock explicit query asset over session state and LLM drift

**Files:**
- Modify: `backend/app/orchestrator/planner.py`
- Test: `backend/tests/test_planner.py`

- [ ] **Step 1: Write the failing tests**

Add tests covering:
- explicit `BTC` query with `current_asset="ETH"` still plans for `BTC`
- LLM decision returning `ETH` for a `BTC` query still produces `BTC` plan slots

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest backend/tests/test_planner.py -q`
Expected: FAIL on the new explicit-asset-priority assertions

- [ ] **Step 3: Write minimal implementation**

Update planner flow so:
- current-message asset extraction happens once
- explicit asset from current query has highest priority
- session `current_asset` is only used when current query has no explicit asset
- LLM decision asset is normalized against the explicit query asset before tasks are built

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest backend/tests/test_planner.py -q`
Expected: PASS

## Chunk 2: Execution Summary Consistency Guard

### Task 2: Prevent mismatched assets from flowing into answer generation

**Files:**
- Modify: `backend/app/orchestrator/orchestrator_service.py`
- Test: `backend/tests/test_orchestrator_service.py`

- [ ] **Step 1: Write the failing test**

Add a test where the current message explicitly asks for `BTC` while session state contains `ETH`, and assert the final `execution_summary["asset"]` remains `BTC`.

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest backend/tests/test_orchestrator_service.py -q`
Expected: FAIL on the new asset-consistency assertion

- [ ] **Step 3: Write minimal implementation**

Add a guard in orchestration that:
- tracks the explicit asset from the current query
- ensures execution summary and final answer path are aligned to that asset
- refuses silent fallback to a stale session asset when the query was explicit

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest backend/tests/test_orchestrator_service.py -q`
Expected: PASS

## Chunk 3: Regression Verification

### Task 3: Verify no regression in the planner-answer pipeline

**Files:**
- Test: `backend/tests/test_planner.py`
- Test: `backend/tests/test_orchestrator_service.py`

- [ ] **Step 1: Run focused regression suite**

Run: `pytest backend/tests/test_planner.py backend/tests/test_orchestrator_service.py -q`
Expected: PASS

- [ ] **Step 2: Run broader backend regression suite**

Run: `pytest backend/tests/test_planner.py backend/tests/test_orchestrator_service.py backend/tests/test_conversation_api.py backend/tests/test_trace_api.py -q`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add backend/app/orchestrator/planner.py backend/app/orchestrator/orchestrator_service.py backend/tests/test_planner.py backend/tests/test_orchestrator_service.py docs/superpowers/plans/2026-03-27-explicit-asset-locking-implementation.md
git commit -m "fix: prioritize explicit query asset in planning"
```
