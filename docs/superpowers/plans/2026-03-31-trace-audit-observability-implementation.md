# Trace Audit Observability Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Upgrade trace observability from a timeline-first log into an audit-first dossier that clearly shows conclusions, evidence provenance, ReAct steps, token/time usage, and LLM callback lifecycle.

**Architecture:** Keep canonical spans as the persisted source of truth, then extend the readable workflow formatter to derive a normalized audit contract with `audit_summary`, `conclusions`, `evidence_records`, `reasoning_steps`, and `timeline`. Update the trace frontend to consume only that normalized contract and render a three-layer audit page: overview strip, conclusion/evidence dossier, and reasoning/timeline drill-down.

**Tech Stack:** FastAPI, Pydantic, Python formatter services, Next.js 15, React 19, TypeScript, existing trace runtime, pytest, ESLint

---

## File Map

### Backend

- Modify: `backend/app/services/readable_trace_formatter.py`
  - Derive the new audit contract from canonical spans and execution summary.
- Modify: `backend/app/api/trace.py`
  - Ensure API returns the new normalized readable workflow shape.
- Modify: `backend/app/services/trace_log_service.py`
  - Preserve any formatter-facing fields needed for callback summary and tool provenance.
- Modify: `backend/app/schemas/execution.py`
  - Extend schemas only if canonical span fields are missing for callback or provenance summaries.
- Test: `backend/tests/test_readable_trace_formatter.py`
  - Formatter derivation, evidence linkage, backward compatibility.
- Test: `backend/tests/test_trace_api.py`
  - API shape and old-trace compatibility.

### Frontend

- Modify: `frontend/lib/api.ts`
  - Add new readable workflow types for audit summary, conclusions, evidence, and reasoning steps.
- Modify: `frontend/components/trace-readable-workflow.tsx`
  - Replace current minimal layout with the new audit-first composition.
- Create: `frontend/components/trace-audit-summary.tsx`
  - Overview strip for status, token, duration, fallback, and model/provider usage.
- Create: `frontend/components/trace-conclusion-dossier.tsx`
  - Final conclusion, missing info, and linked evidence badges.
- Create: `frontend/components/trace-evidence-dossier.tsx`
  - Evidence groups with source domain/tool, summary, and linked conclusion chips.
- Create: `frontend/components/trace-reasoning-steps.tsx`
  - Step cards showing decision summary, action, observation, callbacks, and new evidence.
- Modify: `frontend/components/trace-timeline.tsx`
  - Keep raw timeline as the low-level drill-down layer, but ensure compatibility with new/old shapes.
- Modify: `frontend/components/trace-detail-panel.tsx`
  - Keep old functionality, but tolerate missing detail sections and display richer audit detail when present.

### Verification

- Run: `pytest backend/tests/test_readable_trace_formatter.py backend/tests/test_trace_api.py -q`
- Run: `npm run lint`
- Run: `npm run build` if the local Next worker is stable; otherwise record the worker limitation and verify via dev server.
- Manual smoke:
  - One research-heavy trace
  - One kline-heavy trace
  - One degraded/insufficient trace

## Chunk 1: Backend Audit Contract

### Task 1: Define the new readable workflow shape in tests

**Files:**
- Modify: `backend/tests/test_readable_trace_formatter.py`
- Modify: `backend/tests/test_trace_api.py`

- [ ] **Step 1: Write failing formatter tests for the new contract**

Add tests that expect:

```python
assert workflow["audit_summary"]["trace_status"] == "success"
assert workflow["conclusions"][0]["kind"] == "final"
assert workflow["evidence_records"][0]["source_tool"] == "search_web"
assert workflow["reasoning_steps"][0]["callback"]["finish_reason"] == "stop"
assert workflow["timeline"]
```

- [ ] **Step 2: Add a backward-compatibility test for old traces**

Use a minimal legacy payload that has spans but no new sections and assert:

```python
assert workflow["audit_summary"]["total_tokens"] == 0
assert workflow["conclusions"] == []
assert workflow["evidence_records"] == []
assert workflow["reasoning_steps"] == []
```

- [ ] **Step 3: Run tests to verify they fail**

Run:

```bash
pytest backend/tests/test_readable_trace_formatter.py backend/tests/test_trace_api.py -q
```

Expected: failures for missing keys such as `audit_summary`, `conclusions`, or `evidence_records`.

- [ ] **Step 4: Commit the red tests**

```bash
git add backend/tests/test_readable_trace_formatter.py backend/tests/test_trace_api.py
git commit -m "test: define trace audit readable workflow contract"
```

### Task 2: Implement formatter derivation for audit summary and conclusions

**Files:**
- Modify: `backend/app/services/readable_trace_formatter.py`
- Modify: `backend/app/api/trace.py`

- [ ] **Step 1: Add `audit_summary` derivation**

Implement helpers that compute:

```python
{
    "trace_status": status,
    "started_at": first_start_ts,
    "ended_at": last_end_ts,
    "duration_ms": total_duration_ms,
    "prompt_tokens": prompt_tokens,
    "completion_tokens": completion_tokens,
    "total_tokens": total_tokens,
    "llm_calls": llm_calls,
    "tool_calls": tool_calls,
    "failed_calls": failed_calls,
    "degraded_calls": degraded_calls,
    "models_used": models_used,
    "providers_used": providers_used,
    "fallback_used": fallback_used,
    "first_failed_span_id": first_failed_span_id,
    "first_failed_step_id": None,
    "callback_summary": {...},
}
```

- [ ] **Step 2: Replace the old top-level overview with `conclusions`**

Derive at least one final conclusion from `final_answer` and `execution_summary`:

```python
[
    {
        "conclusion_id": "final",
        "kind": "final",
        "text": final_answer or summary or "",
        "status": status,
        "summary": summary,
        "missing_information": missing_information,
        "evidence_ids": [],
        "derived_from_step_ids": [],
    }
]
```

- [ ] **Step 3: Keep the old `timeline` derivation intact**

Do not remove timeline generation. It remains the fallback-safe low-level layer.

- [ ] **Step 4: Return the new shape from the API**

Ensure `fetchTrace` responses include:

```python
{
    "readable_workflow": {
        "audit_summary": ...,
        "conclusions": [...],
        "evidence_records": [],
        "reasoning_steps": [],
        "timeline": [...],
    }
}
```

- [ ] **Step 5: Run formatter/API tests**

Run:

```bash
pytest backend/tests/test_readable_trace_formatter.py backend/tests/test_trace_api.py -q
```

Expected: PASS for summary and conclusion derivation tests.

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/readable_trace_formatter.py backend/app/api/trace.py
git commit -m "feat: add trace audit summary and conclusions contract"
```

## Chunk 2: Evidence and Reasoning Step Derivation

### Task 3: Derive search and fetch evidence records

**Files:**
- Modify: `backend/tests/test_readable_trace_formatter.py`
- Modify: `backend/app/services/readable_trace_formatter.py`

- [ ] **Step 1: Write failing tests for evidence records**

Add span fixtures for `search_web` and `fetch_page` and expect records like:

```python
assert any(item["source_tool"] == "search_web" for item in evidence_records)
assert any(item["source_domain"] == "coindesk.com" for item in evidence_records)
assert any(item["attributes"]["provider"] == "exa" for item in evidence_records)
assert any(item["attributes"]["strategy"] == "readability_like" for item in evidence_records)
```

- [ ] **Step 2: Implement search evidence derivation**

Map `search_web` tool spans into one parent record and zero or more result records based on:

- input query
- output provider
- output items or result list
- selected URLs if present

- [ ] **Step 3: Implement fetch evidence derivation**

Map `fetch_page` spans into page evidence using:

- input URL
- output title
- output strategy
- output content summary
- error or failure reason

- [ ] **Step 4: Run formatter tests**

Run:

```bash
pytest backend/tests/test_readable_trace_formatter.py -q
```

Expected: PASS for evidence derivation tests.

- [ ] **Step 5: Commit**

```bash
git add backend/tests/test_readable_trace_formatter.py backend/app/services/readable_trace_formatter.py
git commit -m "feat: derive evidence records from search and fetch tool spans"
```

### Task 4: Derive ReAct reasoning steps and callback summary

**Files:**
- Modify: `backend/tests/test_readable_trace_formatter.py`
- Modify: `backend/app/services/readable_trace_formatter.py`
- Modify: `backend/app/services/trace_log_service.py` only if missing callback-facing fields

- [ ] **Step 1: Write failing tests for reasoning steps**

Expect:

```python
assert workflow["reasoning_steps"][0]["decision_summary"] == "Search for recent BTC sentiment sources."
assert workflow["reasoning_steps"][0]["action"] == "search_web"
assert workflow["reasoning_steps"][0]["callback"]["started_at"]
assert workflow["reasoning_steps"][0]["callback"]["finish_reason"] == "stop"
```

- [ ] **Step 2: Group llm and tool spans into step records**

Use parent/child relationships or sequential ordering to derive step records with:

- decision summary
- action
- args
- observation summary
- new evidence ids
- duration
- llm span id
- tool span id

- [ ] **Step 3: Derive callback lifecycle summary**

Use llm span attributes or output summaries to capture:

- started
- first token time if present
- completed
- finish reason
- error

If first-token data is absent, populate `None` and keep the shape stable.

- [ ] **Step 4: Fill `first_failed_step_id` in audit summary**

The first failed step should be identified from the reasoning step list.

- [ ] **Step 5: Run backend tests**

Run:

```bash
pytest backend/tests/test_readable_trace_formatter.py backend/tests/test_trace_api.py -q
```

Expected: PASS for reasoning step and callback tests.

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/readable_trace_formatter.py backend/app/services/trace_log_service.py backend/tests/test_readable_trace_formatter.py backend/tests/test_trace_api.py
git commit -m "feat: add reasoning steps and callback audit summaries"
```

## Chunk 3: Frontend Audit-First Trace Page

### Task 5: Add the new readable workflow types

**Files:**
- Modify: `frontend/lib/api.ts`

- [ ] **Step 1: Add types for audit summary, conclusions, evidence, and reasoning steps**

Define:

```ts
export type TraceAuditSummary = { ... }
export type TraceConclusion = { ... }
export type TraceEvidenceRecord = { ... }
export type TraceReasoningStep = { ... }
```

Keep all fields nullable or optional where legacy traces may omit them.

- [ ] **Step 2: Update `ReadableWorkflow`**

Make it:

```ts
export type ReadableWorkflow = {
  audit_summary?: TraceAuditSummary | null;
  conclusions?: TraceConclusion[] | null;
  evidence_records?: TraceEvidenceRecord[] | null;
  reasoning_steps?: TraceReasoningStep[] | null;
  timeline?: TraceTimelineNode[] | null;
};
```

- [ ] **Step 3: Run lint**

Run:

```bash
npm run lint
```

Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add frontend/lib/api.ts
git commit -m "feat: add trace audit readable workflow types"
```

### Task 6: Build the audit overview and conclusion/evidence dossier

**Files:**
- Create: `frontend/components/trace-audit-summary.tsx`
- Create: `frontend/components/trace-conclusion-dossier.tsx`
- Create: `frontend/components/trace-evidence-dossier.tsx`
- Modify: `frontend/components/trace-readable-workflow.tsx`

- [ ] **Step 1: Add the audit summary component**

Render cards for:

- status
- duration
- total tokens
- llm calls
- tool calls
- failures
- models used
- fallback used

- [ ] **Step 2: Add the conclusion dossier**

Render:

- final conclusion text
- status chip
- missing information
- degraded reason
- linked evidence counts

- [ ] **Step 3: Add the evidence dossier**

Group evidence records by type and show cards with:

- source domain or tool
- title
- summary
- capture time
- linked conclusion ids

Special handling:

- `search_web`: show query, provider, and returned/selected sites
- `fetch_page`: show URL, strategy, and extraction summary

- [ ] **Step 4: Compose the new top half of the trace page**

Replace the current single conclusion block with:

```tsx
<TraceAuditSummary summary={workflow.audit_summary} />
<TraceConclusionDossier conclusions={workflow.conclusions} evidence={workflow.evidence_records} />
<TraceEvidenceDossier evidence={workflow.evidence_records} conclusions={workflow.conclusions} />
```

- [ ] **Step 5: Run lint**

Run:

```bash
npm run lint
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add frontend/components/trace-audit-summary.tsx frontend/components/trace-conclusion-dossier.tsx frontend/components/trace-evidence-dossier.tsx frontend/components/trace-readable-workflow.tsx
git commit -m "feat: add trace audit summary and evidence dossier UI"
```

## Chunk 4: Reasoning Steps and Timeline Compatibility

### Task 7: Add reasoning steps UI

**Files:**
- Create: `frontend/components/trace-reasoning-steps.tsx`
- Modify: `frontend/components/trace-readable-workflow.tsx`

- [ ] **Step 1: Add reasoning step cards**

Each card should show:

- step number
- agent
- decision summary
- action
- args
- observation summary
- newly added evidence
- duration
- tokens
- callback summary

- [ ] **Step 2: Render callback lifecycle compactly**

Show:

- started
- first token latency
- completed or failed
- finish reason

- [ ] **Step 3: Insert reasoning steps between dossier and timeline**

The page order should become:

```tsx
Audit Summary
Conclusion + Evidence
Reasoning Steps
Execution Timeline
```

- [ ] **Step 4: Run lint**

Run:

```bash
npm run lint
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/components/trace-reasoning-steps.tsx frontend/components/trace-readable-workflow.tsx
git commit -m "feat: add reasoning steps audit UI"
```

### Task 8: Harden timeline and detail panel for legacy traces

**Files:**
- Modify: `frontend/components/trace-timeline.tsx`
- Modify: `frontend/components/trace-detail-panel.tsx`

- [ ] **Step 1: Add failing regression checks via manual reproduction notes**

Document and reproduce these legacy compatibility cases:

- no audit summary
- no meta
- no metrics
- no detail tabs

- [ ] **Step 2: Normalize missing fields at component boundaries**

Ensure the timeline never assumes:

- `meta.first_failed_span_id`
- `node.metrics`
- `node.detail_tabs`

- [ ] **Step 3: Eliminate render instability**

Use stable fallback keys and default objects so old traces render instead of crashing.

- [ ] **Step 4: Run lint and manual `/traces` smoke**

Run:

```bash
npm run lint
```

Then manually load `/traces` on:

- one new trace
- one old trace

Expected: both render without runtime exceptions.

- [ ] **Step 5: Commit**

```bash
git add frontend/components/trace-timeline.tsx frontend/components/trace-detail-panel.tsx
git commit -m "fix: harden trace timeline for legacy audit payloads"
```

## Chunk 5: End-to-End Verification

### Task 9: Backend and frontend regression pass

**Files:**
- No code changes expected unless regressions appear

- [ ] **Step 1: Run focused backend tests**

Run:

```bash
pytest backend/tests/test_readable_trace_formatter.py backend/tests/test_trace_api.py -q
```

Expected: PASS.

- [ ] **Step 2: Run broader trace-related backend tests**

Run:

```bash
pytest backend/tests/test_trace_log.py backend/tests/test_orchestrator_service.py backend/tests/test_conversation_api.py -q
```

Expected: PASS.

- [ ] **Step 3: Run frontend lint**

Run:

```bash
npm run lint
```

Expected: PASS.

- [ ] **Step 4: Run frontend build**

Run:

```bash
npm run build
```

Expected: PASS. If the Next worker exits without a useful stack again, record it as an environment limitation and verify through the dev server plus lint instead.

- [ ] **Step 5: Manual smoke test**

Create or inspect:

1. research-heavy trace with `search_web` and `fetch_page`
2. kline-heavy trace with multi-timeframe tools
3. degraded trace with fallback or insufficient evidence

Verify on `/traces`:

- websites searched are visible
- fetched URLs and extracted summaries are visible
- conclusions link to evidence
- reasoning steps show action and observation
- token and duration data are visible
- callback and fallback information are visible
- raw timeline remains available

- [ ] **Step 6: Final commit**

```bash
git add backend/app/services/readable_trace_formatter.py backend/app/api/trace.py backend/app/services/trace_log_service.py backend/tests/test_readable_trace_formatter.py backend/tests/test_trace_api.py frontend/lib/api.ts frontend/components/trace-readable-workflow.tsx frontend/components/trace-audit-summary.tsx frontend/components/trace-conclusion-dossier.tsx frontend/components/trace-evidence-dossier.tsx frontend/components/trace-reasoning-steps.tsx frontend/components/trace-timeline.tsx frontend/components/trace-detail-panel.tsx
git commit -m "feat: add audit-first trace observability dossier"
```
