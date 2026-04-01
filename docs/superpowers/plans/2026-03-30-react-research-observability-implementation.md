# ReAct Research Observability Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Upgrade `ResearchAgent` into a real single-LLM ReAct agent, add unified tool and trace runtimes, and ship a timeline-first `/traces` UI that exposes token usage, tool calls, failures, and audit context without breaking existing Binance and legacy trace flows.

**Architecture:** Keep the existing `Planner -> Executor -> Agents -> SummaryAgent` entry points intact while introducing a reusable backend runtime layer. New `ToolRuntime`, `TraceRuntime`, `ReActLoopService`, and `ResearchResultAssembler` units sit underneath `ResearchAgent`, and trace persistence upgrades from loose events to canonical `spans + metrics_summary` with server-side legacy fallback. The frontend continues to consume `/api/traces`, but switches the detail view to a status-first timeline with a fixed overview bar and node-level drill-down.

**Tech Stack:** Python, FastAPI, Pydantic, Next.js, React, pytest, npm

---

## File Structure

### Backend runtime and schemas

- Create: `backend/app/runtime/tool_contracts.py`
  Own `ToolSpec`, `ToolResult`, `Observation`, `ReActStepOutput`, and shared typed aliases used by runtime, agents, and trace services.
- Create: `backend/app/runtime/tool_runtime.py`
  Resolve tool names to executors, validate args against allowed schemas, execute local or MCP-backed tools, and return normalized `ToolResult`.
- Create: `backend/app/runtime/trace_runtime.py`
  Start, finish, and aggregate canonical spans; compute summary metrics; redact large payloads before persistence.
- Create: `backend/app/runtime/react_loop_service.py`
  Run the bounded single-LLM ReAct loop, parse structured decisions, enforce stop conditions, and emit llm/tool spans through `TraceRuntime`.
- Create: `backend/app/agents/research_result_assembler.py`
  Deterministically transform `ReActTerminalState + Observation[] + ToolResult[]` into `ResearchAgentResult`.
- Create: `backend/app/agents/tools/market_tools.py`
  Wrap existing Binance and external market/protocol fetches as tool executors so `ResearchAgent` can call `research + market` tools through one runtime.

### Backend integrations

- Modify: `backend/app/agents/research_agent.py`
  Replace the hard-coded loop with runtime wiring, initial context assembly, and structured result mapping.
- Modify: `backend/app/agents/tools/research_tools.py`
  Keep executor logic focused on raw search/fetch operations and make outputs compatible with `ToolRuntime`.
- Modify: `backend/app/orchestrator/executor.py`
  Thread runtime-backed research results into `TaskResult`.
- Modify: `backend/app/orchestrator/orchestrator_service.py`
  Consume canonical spans for trace status, summary aggregation, and loop/task event compatibility.
- Modify: `backend/app/services/trace_log_service.py`
  Persist and read new trace payloads, derive pseudo spans for legacy traces, and expose summary fields for trace index screens.
- Modify: `backend/app/services/readable_trace_formatter.py`
  Render readable workflow from canonical spans and fallback pseudo spans.
- Modify: `backend/app/services/conversation_service.py`
  Record answer-generation llm spans and propagate final status/cancellation semantics.
- Modify: `backend/app/api/trace.py`
  Return normalized traces with `spans`, `metrics_summary`, `tool_usage_summary`, and readable workflow.
- Modify: `backend/app/schemas/execution.py`
  Add canonical span, metrics, audit, and summary models.
- Modify: `backend/app/schemas/task_result.py`
  Carry typed `tool_calls`, rounds used, degraded reasons, and evidence status from new research results.

### Frontend trace UI

- Modify: `frontend/lib/api.ts`
  Add types for spans, metrics summary, tool usage summary, detail tabs, and legacy fallback fields.
- Modify: `frontend/app/traces/page.tsx`
  Switch to the timeline-first detail layout and wire detail panel state.
- Create: `frontend/components/trace-overview-strip.tsx`
  Render top-level status, token, tool, failure, and duration cards.
- Create: `frontend/components/trace-timeline.tsx`
  Render ordered planner/agent/llm/tool/summary nodes, filters, and first-failure auto focus.
- Create: `frontend/components/trace-detail-panel.tsx`
  Render `Input / Output / Error / Audit` tabs for the selected span.
- Modify: `frontend/components/trace-raw-events.tsx`
  Keep raw JSON fallback available behind a collapsed panel.

### Tests

- Create: `backend/tests/test_tool_runtime.py`
- Create: `backend/tests/test_trace_runtime.py`
- Create: `backend/tests/test_react_loop_service.py`
- Create: `backend/tests/test_research_result_assembler.py`
- Modify: `backend/tests/test_research_agent.py`
- Modify: `backend/tests/test_research_tools.py`
- Modify: `backend/tests/test_orchestrator_service.py`
- Modify: `backend/tests/test_trace_log.py`
- Modify: `backend/tests/test_trace_api.py`
- Modify: `backend/tests/test_readable_trace_formatter.py`

## Chunk 1: Runtime Contracts And Canonical Trace Schema

### Task 1: Lock down runtime and trace contracts with failing tests

**Files:**
- Create: `backend/tests/test_tool_runtime.py`
- Create: `backend/tests/test_trace_runtime.py`
- Modify: `backend/tests/test_trace_log.py`
- Modify: `backend/tests/test_trace_api.py`

- [ ] **Step 1: Write the failing `ToolRuntime` contract tests**

Cover these cases with explicit fixtures:
- `ToolRuntime.execute()` returns a normalized `ToolResult` on success
- unknown tool names return `status="failed"` with `reason="unknown_tool"`
- schema-invalid args do not execute the underlying tool and return `status="degraded"`
- MCP-backed tools and local tools both produce the same top-level keys

- [ ] **Step 2: Run the focused tool runtime tests to verify they fail**

Run: `pytest backend/tests/test_tool_runtime.py -q`
Expected: FAIL because `ToolRuntime`, `ToolSpec`, and `ToolResult` do not exist yet.

- [ ] **Step 3: Write the failing `TraceRuntime` contract tests**

Add tests that assert:
- `start_span()` returns a span with `span_id`, `parent_span_id`, `kind`, `attributes`, `metrics`, and `audit`
- `finish_span()` computes `duration_ms` and merges `attributes`
- `finalize_trace()` produces `metrics_summary`, `tool_usage_summary`, `llm_call_count`, `tool_call_count`, and `failure_count`
- large tool outputs are truncated before persistence with an explicit truncation flag
- `audit_level="sensitive"` tool spans redact raw args and output fields before persistence while preserving summary-safe previews
- legacy fallback spans use `status="unknown"` when no better status can be derived

- [ ] **Step 4: Run the focused trace runtime tests to verify they fail**

Run: `pytest backend/tests/test_trace_runtime.py -q`
Expected: FAIL because `TraceRuntime` and the new summary schema do not exist yet.

- [ ] **Step 5: Extend trace persistence tests before implementation**

In `backend/tests/test_trace_log.py` and `backend/tests/test_trace_api.py`, add failing assertions for:
- persisted traces including `spans`, `metrics_summary`, and `tool_usage_summary`
- persisted summaries keeping top-level `status`, `error_summary`, and `agent_summaries`
- legacy traces being normalized into `pseudo_spans`
- `/api/traces/{trace_id}` returning both readable workflow and canonical spans

- [ ] **Step 6: Run the persistence and API tests to verify they fail**

Run: `pytest backend/tests/test_trace_log.py backend/tests/test_trace_api.py -q`
Expected: FAIL because persisted trace payloads and API output still use the old event-only shape.

### Task 2: Implement runtime contracts and trace persistence

**Files:**
- Create: `backend/app/runtime/tool_contracts.py`
- Create: `backend/app/runtime/tool_runtime.py`
- Create: `backend/app/runtime/trace_runtime.py`
- Modify: `backend/app/schemas/execution.py`
- Modify: `backend/app/services/trace_log_service.py`
- Modify: `backend/app/api/trace.py`
- Test: `backend/tests/test_tool_runtime.py`
- Test: `backend/tests/test_trace_runtime.py`
- Test: `backend/tests/test_trace_log.py`
- Test: `backend/tests/test_trace_api.py`

- [ ] **Step 1: Add typed runtime contracts**

Define typed aliases and models for:
- `ToolSpec`
- `ToolResult`
- `Observation`
- `ReActStepOutput`
- span `metrics`
- span `audit`
- trace `metrics_summary`
- trace `tool_usage_summary`

Keep low-level types narrow enough for tests to assert exact keys, but do not pull in a second schema system beyond Pydantic and `TypedDict`.

- [ ] **Step 2: Implement minimal `ToolRuntime`**

Build a registry-driven executor that:
- looks up tool specs by name
- validates args against the allowed JSON-schema subset
- calls either a local Python executor or the MCP registry wrapper
- normalizes success, degraded, and failed results into one `ToolResult` shape
- records `input_bytes` and `output_bytes`

- [ ] **Step 3: Implement minimal `TraceRuntime`**

Support:
- `start_span()`
- `finish_span()`
- `record_error()`
- `finalize_trace()`

`finalize_trace()` must aggregate:
- prompt, completion, and total tokens
- total input and output bytes
- tool call totals
- failed and degraded tool counts
- llm call count and failure count
- top-level `status`
- `error_summary`
- `agent_summaries`

- [ ] **Step 4: Upgrade trace persistence and read-path compatibility**

Teach `TraceLogService` and `/api/traces/{trace_id}` to:
- persist canonical `spans`
- keep old `plan`, `task_results`, `events`, and `execution_summary`
- backfill `pseudo_spans` from old traces on read
- surface summary cards from `metrics_summary` instead of recalculating in the frontend
- apply spec-defined redaction rules for sensitive spans before writing trace files
- leave readable-workflow generation on the current path until Chunk 3, but return enough canonical fields now for that formatter migration

- [ ] **Step 5: Run the backend tests for this chunk**

Run: `pytest backend/tests/test_tool_runtime.py backend/tests/test_trace_runtime.py backend/tests/test_trace_log.py backend/tests/test_trace_api.py -q`
Expected: PASS

- [ ] **Step 6: Commit the runtime contract chunk**

```bash
git add backend/app/runtime/tool_contracts.py backend/app/runtime/tool_runtime.py backend/app/runtime/trace_runtime.py backend/app/schemas/execution.py backend/app/services/trace_log_service.py backend/app/api/trace.py backend/tests/test_tool_runtime.py backend/tests/test_trace_runtime.py backend/tests/test_trace_log.py backend/tests/test_trace_api.py docs/superpowers/plans/2026-03-30-react-research-observability-implementation.md
git commit -m "feat: add canonical trace and tool runtime contracts"
```

## Chunk 2: Single-LLM ReAct Research Agent

### Task 3: Specify the ReAct loop and result assembly with failing tests

**Files:**
- Create: `backend/tests/test_react_loop_service.py`
- Create: `backend/tests/test_research_result_assembler.py`
- Modify: `backend/tests/test_research_agent.py`
- Modify: `backend/tests/test_orchestrator_service.py`

- [ ] **Step 1: Write the failing ReAct loop tests**

Cover these cases:
- valid structured model output selects a tool and produces one `llm` span plus one `tool` span
- invalid JSON stops the loop with `status="failed"`
- `termination=true` with non-empty action stops with degraded metadata
- unknown or disallowed tool names produce a degraded llm step and no tool execution
- `termination=false` with an empty action fails the current llm step
- non-object `args` fails the current llm step
- repeated identical tool calls stop with `status="insufficient"`
- tool failures beyond the threshold stop the loop with `status="failed"`
- `termination=true` with insufficient evidence ends the loop but forces terminal `evidence_status="insufficient"`

- [ ] **Step 2: Run the ReAct loop tests to verify they fail**

Run: `pytest backend/tests/test_react_loop_service.py -q`
Expected: FAIL because `ReActLoopService` does not exist yet.

- [ ] **Step 3: Write the failing assembler and agent integration tests**

Add assertions that:
- `ResearchResultAssembler` derives `summary`, `findings`, `risks`, `catalysts`, and `degraded_reason` from observations and tool results
- `ResearchAgent.execute("protocol_due_diligence", ...)` returns a typed `ResearchAgentResult`
- `tool_calls` are normalized `ToolResult` objects rather than ad hoc dicts
- `rounds_used`, `termination_reason`, `missing_information`, and `evidence_status` propagate into `TaskResult` and `execution_summary`
- `evidence_status` maps into `TaskResult.evidence_sufficient` exactly as defined in the spec

- [ ] **Step 4: Run the assembler, research agent, and orchestrator tests to verify they fail**

Run: `pytest backend/tests/test_research_result_assembler.py backend/tests/test_research_agent.py backend/tests/test_orchestrator_service.py -q`
Expected: FAIL because the research path still uses the hard-coded loop and old payload structure.

### Task 4: Implement ReAct loop services and wire `ResearchAgent`

**Files:**
- Create: `backend/app/runtime/react_loop_service.py`
- Create: `backend/app/agents/research_result_assembler.py`
- Create: `backend/app/agents/tools/market_tools.py`
- Modify: `backend/app/agents/research_agent.py`
- Modify: `backend/app/agents/tools/research_tools.py`
- Modify: `backend/app/orchestrator/executor.py`
- Modify: `backend/app/orchestrator/orchestrator_service.py`
- Modify: `backend/app/schemas/task_result.py`
- Test: `backend/tests/test_react_loop_service.py`
- Test: `backend/tests/test_research_result_assembler.py`
- Test: `backend/tests/test_research_agent.py`
- Test: `backend/tests/test_orchestrator_service.py`

- [ ] **Step 1: Implement `ReActLoopService` with bounded stop rules**

The loop must:
- inject only the allowed `research + market` tool specs
- call the configured LLM once per round
- parse a structured action object
- route the action through `ToolRuntime`
- append an `Observation`
- enforce `max_rounds`, repeated-call, failure-count, and no-progress guards
- implement the full malformed-output table from the spec before any fallback behavior is added
- stop early when evidence is sufficient, and downgrade terminal status to `insufficient` when the model stops without enough evidence
- write llm and tool spans through `TraceRuntime`

- [ ] **Step 2: Implement `ResearchResultAssembler`**

Make it deterministic. It should:
- compress the terminal state into `summary`
- deduplicate factual `findings`
- pull risk items from market and protocol observations
- surface `missing_information`
- join degraded reasons from degraded tool results

- [ ] **Step 3: Convert existing market and research helpers into runtime tools**

Wrap:
- `search_web`
- `fetch_page`
- `read_asset_memory`
- `get_market_snapshot`
- `get_protocol_snapshot`
- `get_ticker`
- `get_klines`

Use the current adapters and services; do not introduce new providers in this chunk.
Keep raw search/fetch implementations in `backend/app/agents/tools/research_tools.py`, and use `backend/app/agents/tools/market_tools.py` only for market/protocol wrappers so ownership stays obvious.

- [ ] **Step 4: Rewire `ResearchAgent` and executor integration**

`ResearchAgent` should now:
- build initial context from the existing external research service and asset memory
- instantiate the runtime tool set
- call `ReActLoopService`
- pass results to `ResearchResultAssembler`
- return the spec-approved `ResearchAgentResult`

Update executor/orchestrator code so `TaskResult` and trace status use the new result shape without breaking `KlineAgent` or `SummaryAgent`.

- [ ] **Step 5: Run the backend tests for this chunk**

Run: `pytest backend/tests/test_react_loop_service.py backend/tests/test_research_result_assembler.py backend/tests/test_research_agent.py backend/tests/test_orchestrator_service.py backend/tests/test_research_tools.py -q`
Expected: PASS

- [ ] **Step 6: Commit the ReAct research chunk**

```bash
git add backend/app/runtime/react_loop_service.py backend/app/agents/research_result_assembler.py backend/app/agents/tools/market_tools.py backend/app/agents/research_agent.py backend/app/agents/tools/research_tools.py backend/app/orchestrator/executor.py backend/app/orchestrator/orchestrator_service.py backend/app/schemas/task_result.py backend/tests/test_react_loop_service.py backend/tests/test_research_result_assembler.py backend/tests/test_research_agent.py backend/tests/test_orchestrator_service.py backend/tests/test_research_tools.py docs/superpowers/plans/2026-03-30-react-research-observability-implementation.md
git commit -m "feat: add react research runtime"
```

## Chunk 3: Readable Trace Formatting And Timeline UI

### Task 5: Lock the trace API and formatter behavior with failing tests

**Files:**
- Modify: `backend/tests/test_readable_trace_formatter.py`
- Modify: `backend/tests/test_trace_api.py`

- [ ] **Step 1: Write the failing readable formatter tests**

Assert that a canonical trace can produce:
- a top summary block with total tokens, tool calls, failures, and duration
- timeline entries ordered by span start time
- a first failure pointer
- detail payloads for `Input`, `Output`, `Error`, and `Audit`
- `clarify` traces render planner-only workflow data without fake tool or llm failures
- `cancelled` traces stop at the last closed span and omit final-answer presentation
- legacy traces still rendering via pseudo spans

- [ ] **Step 2: Run the formatter tests to verify they fail**

Run: `pytest backend/tests/test_readable_trace_formatter.py -q`
Expected: FAIL because the formatter only understands legacy task/event payloads.

- [ ] **Step 3: Extend trace API tests for timeline payload shape**

Add failing assertions for:
- `spans` sorted and normalized
- `metrics_summary` and `tool_usage_summary` in the response body
- `readable_workflow.meta.first_failed_span_id`
- `clarify` and `cancelled` traces preserving their special top-level status rules
- raw events preserved for collapsed diagnostics

- [ ] **Step 4: Run the trace API tests to verify they fail**

Run: `pytest backend/tests/test_trace_api.py -q`
Expected: FAIL because the trace API does not yet expose the new timeline-oriented fields.

### Task 6: Implement readable formatter and frontend trace timeline

**Files:**
- Modify: `backend/app/services/readable_trace_formatter.py`
- Modify: `backend/app/services/conversation_service.py`
- Modify: `backend/app/api/trace.py`
- Modify: `frontend/lib/api.ts`
- Modify: `frontend/app/traces/page.tsx`
- Create: `frontend/components/trace-overview-strip.tsx`
- Create: `frontend/components/trace-timeline.tsx`
- Create: `frontend/components/trace-detail-panel.tsx`
- Modify: `frontend/components/trace-raw-events.tsx`
- Test: `backend/tests/test_readable_trace_formatter.py`
- Test: `backend/tests/test_trace_api.py`

- [ ] **Step 1: Upgrade the readable formatter**

Make the formatter emit frontend-friendly data for:
- overview cards
- ordered timeline nodes
- detail tabs
- first failure anchor
- `clarify` and `cancelled` state handling
- legacy pseudo-span fallback

- [ ] **Step 2: Capture final answer generation in the trace**

Update `ConversationService` so answer-generation llm spans contribute token counts, durations, and cancellation/failure semantics to the same canonical trace.

- [ ] **Step 3: Extend frontend trace types**

Add types for:
- `TraceSpan`
- `TraceMetricsSummary`
- `ToolUsageSummary`
- `TraceTimelineNode`
- `TraceDetailTabs`

Keep nullable fallback fields where history traces might not contain the new values.

- [ ] **Step 4: Build the timeline-first trace detail view**

Implement:
- a top overview strip with six cards
- filterable timeline nodes for `All / Failed Only / LLM / Tool`
- automatic focus on the first failed span when one exists
- a bottom detail panel with `Input / Output / Error / Audit`
- a collapsed raw-events section at the bottom
- responsive behavior matching the spec: compact overview grid on mobile, single-column timeline, and detail panel stacked below the timeline
- special-case UI states for `clarify` and `cancelled`

- [ ] **Step 5: Run backend and frontend verification for this chunk**

Run: `pytest backend/tests/test_readable_trace_formatter.py backend/tests/test_trace_api.py -q`
Expected: PASS

Run: `cd frontend && npm run lint`
Expected: PASS

- [ ] **Step 6: Commit the trace UI chunk**

```bash
git add backend/app/services/readable_trace_formatter.py backend/app/services/conversation_service.py backend/app/api/trace.py frontend/lib/api.ts frontend/app/traces/page.tsx frontend/components/trace-overview-strip.tsx frontend/components/trace-timeline.tsx frontend/components/trace-detail-panel.tsx frontend/components/trace-raw-events.tsx backend/tests/test_readable_trace_formatter.py backend/tests/test_trace_api.py docs/superpowers/plans/2026-03-30-react-research-observability-implementation.md
git commit -m "feat: add timeline trace observability ui"
```

## Chunk 4: End-To-End Verification And Cleanup

### Task 7: Run the regression suite and finish the branch cleanly

**Files:**
- Test: `backend/tests/test_tool_runtime.py`
- Test: `backend/tests/test_trace_runtime.py`
- Test: `backend/tests/test_react_loop_service.py`
- Test: `backend/tests/test_research_result_assembler.py`
- Test: `backend/tests/test_research_agent.py`
- Test: `backend/tests/test_research_tools.py`
- Test: `backend/tests/test_orchestrator_service.py`
- Test: `backend/tests/test_trace_log.py`
- Test: `backend/tests/test_trace_api.py`
- Test: `backend/tests/test_readable_trace_formatter.py`
- Test: `frontend/app/traces/page.tsx`

- [ ] **Step 1: Run the backend regression suite**

Run: `pytest backend/tests/test_tool_runtime.py backend/tests/test_trace_runtime.py backend/tests/test_react_loop_service.py backend/tests/test_research_result_assembler.py backend/tests/test_research_agent.py backend/tests/test_research_tools.py backend/tests/test_orchestrator_service.py backend/tests/test_trace_log.py backend/tests/test_trace_api.py backend/tests/test_readable_trace_formatter.py -q`
Expected: PASS

- [ ] **Step 2: Run the frontend production verification**

Run: `cd frontend && npm run build`
Expected: PASS

- [ ] **Step 3: Do one manual trace smoke test**

Run the app locally, execute one research-heavy query and one kline-heavy query, then confirm in `/traces`:
- overview cards show totals
- a tool span appears for market and research tools
- a forced failure shows a highlighted failed node
- a `clarify` trace renders without fake execution nodes
- a cancelled trace hides the final answer card and ends at the last completed span
- old traces still render instead of crashing
- the page remains readable in a narrow/mobile viewport

- [ ] **Step 4: Commit the final verification pass**

```bash
git add docs/superpowers/plans/2026-03-30-react-research-observability-implementation.md
git commit -m "chore: verify react research observability rollout"
```
