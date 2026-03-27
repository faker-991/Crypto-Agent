# Research Agent Loop Trace Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn `ResearchAgent` into a bounded observe-decide-act loop and surface each loop round in `/traces` as a readable execution timeline.

**Architecture:** Keep the existing planner-executor-summary pipeline unchanged at the interface level. Implement the loop entirely inside `ResearchAgent`, store round-by-round state in `payload.agent_loop`, teach the readable trace formatter to extract loop rounds, and extend the trace UI to render them without breaking old traces.

**Tech Stack:** Python, FastAPI service layer, Pydantic, React/Next.js, pytest

---

## Chunk 1: Research Agent Loop Contract

### Task 1: Define loop payload behavior with failing tests

**Files:**
- Modify: `backend/tests/test_readable_trace_formatter.py`
- Create or Modify: `backend/tests/test_research_agent.py`

- [ ] **Step 1: Write the failing test for research loop payload**

Add a test that runs `ResearchAgent` with stubbed toolbox responses and asserts:
- `payload["agent_loop"]` exists
- loop entries contain `round`, `decision`, `action`, `result`, `state_update`
- `rounds_used` equals actual loop count
- `termination_reason` is recorded

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest backend/tests/test_research_agent.py -q`
Expected: FAIL because `agent_loop` and loop metadata do not exist yet

- [ ] **Step 3: Write the failing trace formatter test**

Add a trace payload fixture with `payload.agent_loop` and assert readable workflow includes human-readable loop rounds for `ResearchAgent`.

- [ ] **Step 4: Run test to verify it fails**

Run: `pytest backend/tests/test_readable_trace_formatter.py -q`
Expected: FAIL because research loop data is not rendered yet

## Chunk 2: Research Agent Loop Implementation

### Task 2: Add bounded observe-decide-act-update loop to `ResearchAgent`

**Files:**
- Modify: `backend/app/agents/research_agent.py`
- Test: `backend/tests/test_research_agent.py`

- [ ] **Step 1: Implement minimal bounded loop**

Update `protocol_due_diligence` so it:
- initializes working state
- loops up to a small max round count
- chooses one action per round from `search_web`, `fetch_page`, `finish`
- tracks seen queries and seen URLs
- stops on evidence sufficiency, no-new-information, or max rounds

- [ ] **Step 2: Include loop trace in payload**

Store:
- `agent_loop`
- `termination_reason`
- `rounds_used`

inside the returned research payload while preserving existing keys like `summary`, `bull_case`, `bear_case`, `risks`, and `tool_calls`.

- [ ] **Step 3: Run focused tests**

Run: `pytest backend/tests/test_research_agent.py -q`
Expected: PASS

## Chunk 3: Readable Trace Formatting

### Task 3: Render loop rounds in readable workflow output

**Files:**
- Modify: `backend/app/services/readable_trace_formatter.py`
- Test: `backend/tests/test_readable_trace_formatter.py`

- [ ] **Step 1: Teach formatter to parse `payload.agent_loop`**

Convert loop rounds into human-readable timeline lines, including:
- round number
- why the round chose its action
- what tool was called
- what new information was gained
- why the loop stopped

- [ ] **Step 2: Expose loop details in stage metadata**

Add loop-specific metadata so the frontend can render a dedicated “循环过程” section without overloading the existing generic bullet blocks.

- [ ] **Step 3: Run focused tests**

Run: `pytest backend/tests/test_readable_trace_formatter.py -q`
Expected: PASS

## Chunk 4: Trace UI Rendering

### Task 4: Show research loop rounds in `/traces`

**Files:**
- Modify: `frontend/lib/api.ts`
- Modify: `frontend/components/trace-readable-workflow.tsx`

- [ ] **Step 1: Extend frontend workflow types**

Add optional loop metadata typing so the UI can safely read new loop rounds while staying backward compatible with older traces.

- [ ] **Step 2: Render a dedicated loop section**

For research stages with loop metadata, render a visible “循环过程” block that lists rounds in order and displays the stop reason.

- [ ] **Step 3: Keep old traces compatible**

If no loop metadata exists, render nothing extra and preserve current stage layout.

- [ ] **Step 4: Run frontend verification**

Run: `cd frontend && npm run lint`
Expected: PASS

## Chunk 5: Regression Verification

### Task 5: Verify end-to-end compatibility

**Files:**
- Test: `backend/tests/test_research_agent.py`
- Test: `backend/tests/test_readable_trace_formatter.py`
- Test: `backend/tests/test_trace_api.py`
- Modify if needed: `frontend/components/trace-readable-workflow.tsx`

- [ ] **Step 1: Run backend regression suite**

Run: `pytest backend/tests/test_research_agent.py backend/tests/test_readable_trace_formatter.py backend/tests/test_trace_api.py -q`
Expected: PASS

- [ ] **Step 2: Run frontend production verification**

Run: `cd frontend && npm run build`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add backend/app/agents/research_agent.py backend/app/services/readable_trace_formatter.py backend/tests/test_research_agent.py backend/tests/test_readable_trace_formatter.py frontend/lib/api.ts frontend/components/trace-readable-workflow.tsx docs/superpowers/plans/2026-03-27-research-agent-loop-trace-implementation.md
git commit -m "feat: add research agent loop trace"
```
