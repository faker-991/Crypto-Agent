# Planner MVP Refactor Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the router-driven top-level execution chain with a planner/orchestrator architecture while preserving the existing UI shell, local memory files, conversations, traces, watchlist, and paper trading features.

**Architecture:** Add a new `orchestrator/` layer with `ContextBuilder`, `Planner`, `Executor`, and `OrchestratorService`, keep `ResearchAgent` and `KlineAgent` as execution units, add `SummaryAgent`, then cut `ConversationService`, API routes, trace semantics, and frontend types/components over to planner terminology before deleting router modules.

**Tech Stack:** FastAPI, Pydantic, pytest, Next.js App Router, TypeScript, ESLint, local JSON/Markdown memory files

---

## Planning Notes

- Current workspace is not initialized as a git repository, so commit steps should be treated as local checkpoints unless git is initialized before execution.
- No frontend test runner exists in the repo today. Frontend verification for this plan uses `npm run lint`, `npm run build`, and manual browser smoke checks.
- Keep scope limited to Planner MVP:
  - single-task kline
  - single-task research
  - multi-task research + kline
  - follow-up resolution

## File Structure

### New backend files

- Create: `backend/app/orchestrator/__init__.py`
- Create: `backend/app/orchestrator/context_builder.py`
- Create: `backend/app/orchestrator/planner.py`
- Create: `backend/app/orchestrator/executor.py`
- Create: `backend/app/orchestrator/orchestrator_service.py`
- Create: `backend/app/agents/summary_agent.py`
- Create: `backend/app/api/planner.py`
- Create: `backend/app/schemas/planning_context.py`
- Create: `backend/app/schemas/task.py`
- Create: `backend/app/schemas/plan.py`
- Create: `backend/app/schemas/task_result.py`
- Create: `backend/app/schemas/planner_response.py`
- Create: `backend/app/services/recent_summary_service.py`

### New backend tests

- Create: `backend/tests/test_planning_schemas.py`
- Create: `backend/tests/test_context_builder.py`
- Create: `backend/tests/test_planner.py`
- Create: `backend/tests/test_executor.py`
- Create: `backend/tests/test_summary_agent.py`
- Create: `backend/tests/test_orchestrator_service.py`
- Create: `backend/tests/test_planner_api.py`

### Existing backend files to modify

- Modify: `backend/app/main.py`
- Modify: `backend/app/services/conversation_service.py`
- Modify: `backend/app/services/trace_log_service.py`
- Modify: `backend/app/schemas/conversation.py`
- Modify: `backend/app/api/conversations.py`
- Modify: `backend/app/services/memory_service.py`
- Modify: `backend/app/services/context_assembly_service.py`
- Modify: `backend/tests/test_conversation_api.py`
- Modify: `backend/tests/test_trace_api.py`
- Modify: `backend/tests/test_trace_log.py`

### Existing frontend files to modify

- Modify: `frontend/lib/api.ts`
- Modify: `frontend/components/router-chat.tsx`
- Modify: `frontend/components/dashboard-client.tsx`
- Modify: `frontend/components/conversation-panel.tsx`
- Modify: `frontend/app/traces/page.tsx`
- Modify: `frontend/app/page.tsx` only if import names change

### Existing files to delete late in the plan

- Delete: `backend/app/services/router_service.py`
- Delete: `backend/app/services/router_llm_service.py`
- Delete: `backend/app/agents/router_agent.py`
- Delete: `backend/app/api/router.py`
- Delete or rename: `backend/tests/test_router_service.py`
- Delete or rename: `backend/tests/test_router_api.py`
- Delete or rename: `backend/tests/test_router_execution.py`
- Delete or rename: `backend/tests/test_router_kline_execution.py`
- Delete or rename: `backend/tests/test_router_binance_execution.py`
- Delete or rename: `backend/tests/test_router_llm_service.py`
- Rename: `frontend/components/router-chat.tsx`

## Chunk 1: Backend Foundation

### Task 1: Add planner schemas

**Files:**
- Create: `backend/app/schemas/planning_context.py`
- Create: `backend/app/schemas/task.py`
- Create: `backend/app/schemas/plan.py`
- Create: `backend/app/schemas/task_result.py`
- Create: `backend/app/schemas/planner_response.py`
- Test: `backend/tests/test_planning_schemas.py`

- [ ] **Step 1: Write the failing schema tests**

Add tests that validate:
- `PlanningContext` accepts session/recent/memory/capability/constraint payloads
- `Task` supports `research`, `kline`, `summary`
- `Plan` supports clarify mode with empty task list
- `PlannerExecutionResponse` supports `execute`, `clarify`, `failed`

- [ ] **Step 2: Run the schema tests to verify they fail**

Run: `cd /home/akalaopaoer/code/crypto-agent/backend && pytest tests/test_planning_schemas.py -v`
Expected: FAIL with import errors for missing planner schema modules

- [ ] **Step 3: Implement the minimal schema modules**

Create the five schema files with focused Pydantic models and shared literals where useful. Keep planner-era naming only; do not alias back to router terminology.

- [ ] **Step 4: Run the schema tests to verify they pass**

Run: `cd /home/akalaopaoer/code/crypto-agent/backend && pytest tests/test_planning_schemas.py -v`
Expected: PASS

- [ ] **Step 5: Local checkpoint**

If git is available:

```bash
git add backend/app/schemas/planning_context.py backend/app/schemas/task.py backend/app/schemas/plan.py backend/app/schemas/task_result.py backend/app/schemas/planner_response.py backend/tests/test_planning_schemas.py
git commit -m "feat: add planner schemas"
```

If git is unavailable, record this task as the first local checkpoint.

### Task 2: Add ContextBuilder and RecentSummaryService

**Files:**
- Create: `backend/app/services/recent_summary_service.py`
- Create: `backend/app/orchestrator/context_builder.py`
- Modify: `backend/app/services/context_assembly_service.py`
- Test: `backend/tests/test_context_builder.py`

- [ ] **Step 1: Write the failing context builder tests**

Add tests that verify:
- current query is preserved in `PlanningContext.user_request.raw_query`
- session state is copied into `session_context`
- recent summaries are bounded to the requested limit
- memory context defaults to an empty list for MVP
- request type marks follow-up queries like `那它周线呢`

- [ ] **Step 2: Run the context builder tests to verify they fail**

Run: `cd /home/akalaopaoer/code/crypto-agent/backend && pytest tests/test_context_builder.py -v`
Expected: FAIL with missing `ContextBuilder` / `RecentSummaryService`

- [ ] **Step 3: Implement `RecentSummaryService` and `ContextBuilder`**

Implementation notes:
- `RecentSummaryService` should read a small recent window from conversation or trace artifacts without introducing a new persistence layer.
- `ContextBuilder` should not decide tasks or route agents.
- `ContextAssemblyService` can keep existing methods, but add or expose helper logic that makes planner context assembly straightforward instead of duplicating file reads everywhere.

- [ ] **Step 4: Run the context builder tests to verify they pass**

Run: `cd /home/akalaopaoer/code/crypto-agent/backend && pytest tests/test_context_builder.py -v`
Expected: PASS

- [ ] **Step 5: Local checkpoint**

If git is available:

```bash
git add backend/app/services/recent_summary_service.py backend/app/orchestrator/context_builder.py backend/app/services/context_assembly_service.py backend/tests/test_context_builder.py
git commit -m "feat: add planner context builder"
```

If git is unavailable, record this task as the second local checkpoint.

### Task 3: Add Planner decision logic

**Files:**
- Create: `backend/app/orchestrator/planner.py`
- Test: `backend/tests/test_planner.py`

- [ ] **Step 1: Write the failing planner tests**

Add tests that verify:
- `看下 BTC 4h` produces a single `kline` task
- `帮我研究一下 SUI 基本面` produces a single `research` task
- `分析 SUI 值不值得继续拿，顺便看下周线和4h走势` produces `research`, `kline`, and dependent `summary`
- `那它周线呢` resolves follow-up from session context
- ambiguous requests without asset produce `needs_clarification=True`

- [ ] **Step 2: Run the planner tests to verify they fail**

Run: `cd /home/akalaopaoer/code/crypto-agent/backend && pytest tests/test_planner.py -v`
Expected: FAIL with missing `Planner`

- [ ] **Step 3: Implement `Planner`**

Implementation notes:
- Keep it deterministic for MVP.
- Do not reintroduce `RouterAgent` naming or route-mapping abstractions.
- Express the output entirely as `Plan` + `Task[]`.

- [ ] **Step 4: Run the planner tests to verify they pass**

Run: `cd /home/akalaopaoer/code/crypto-agent/backend && pytest tests/test_planner.py -v`
Expected: PASS

- [ ] **Step 5: Local checkpoint**

If git is available:

```bash
git add backend/app/orchestrator/planner.py backend/tests/test_planner.py
git commit -m "feat: add planner task decomposition"
```

If git is unavailable, record this task as the third local checkpoint.

### Task 4: Add Executor and SummaryAgent

**Files:**
- Create: `backend/app/orchestrator/executor.py`
- Create: `backend/app/agents/summary_agent.py`
- Test: `backend/tests/test_executor.py`
- Test: `backend/tests/test_summary_agent.py`

- [ ] **Step 1: Write the failing executor and summary agent tests**

Add tests that verify:
- `research` tasks call `ResearchAgent`
- `kline` tasks call `KlineAgent`
- `summary` tasks consume prior `TaskResult[]`
- task execution order respects `depends_on`
- summary output includes `final_answer` plus an `execution_summary`

- [ ] **Step 2: Run the executor and summary tests to verify they fail**

Run: `cd /home/akalaopaoer/code/crypto-agent/backend && pytest tests/test_executor.py tests/test_summary_agent.py -v`
Expected: FAIL with missing executor / summary modules

- [ ] **Step 3: Implement `Executor` and `SummaryAgent`**

Implementation notes:
- Use sequential execution only.
- Keep agents thinly wrapped; do not rewrite `ResearchAgent` or `KlineAgent` behavior beyond the adapter needed for task execution.
- Keep summary behavior deterministic at first if that reduces scope.

- [ ] **Step 4: Run the executor and summary tests to verify they pass**

Run: `cd /home/akalaopaoer/code/crypto-agent/backend && pytest tests/test_executor.py tests/test_summary_agent.py -v`
Expected: PASS

- [ ] **Step 5: Local checkpoint**

If git is available:

```bash
git add backend/app/orchestrator/executor.py backend/app/agents/summary_agent.py backend/tests/test_executor.py backend/tests/test_summary_agent.py
git commit -m "feat: add planner executor and summary agent"
```

If git is unavailable, record this task as the fourth local checkpoint.

### Task 5: Add OrchestratorService and planner API

**Files:**
- Create: `backend/app/orchestrator/orchestrator_service.py`
- Create: `backend/app/api/planner.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_orchestrator_service.py`
- Test: `backend/tests/test_planner_api.py`

- [ ] **Step 1: Write the failing orchestrator and planner API tests**

Add tests that verify:
- clarify path returns `status="clarify"` with no task execution
- execute path returns `plan`, `task_results`, `final_answer`, `events`
- planner API is mounted at `/api/planner/execute`
- `main.py` injects `OrchestratorService` into the new planner API

- [ ] **Step 2: Run the orchestrator and planner API tests to verify they fail**

Run: `cd /home/akalaopaoer/code/crypto-agent/backend && pytest tests/test_orchestrator_service.py tests/test_planner_api.py -v`
Expected: FAIL with missing orchestrator service / planner API route

- [ ] **Step 3: Implement `OrchestratorService`, planner API, and app wiring**

Implementation notes:
- Create new trace events with planner terminology only.
- Wire `main.py` to include the planner router.
- Keep the old router router mounted for now only if needed to avoid a half-cut application state during implementation; remove it in Chunk 2.

- [ ] **Step 4: Run the orchestrator and planner API tests to verify they pass**

Run: `cd /home/akalaopaoer/code/crypto-agent/backend && pytest tests/test_orchestrator_service.py tests/test_planner_api.py -v`
Expected: PASS

- [ ] **Step 5: Local checkpoint**

If git is available:

```bash
git add backend/app/orchestrator/orchestrator_service.py backend/app/api/planner.py backend/app/main.py backend/tests/test_orchestrator_service.py backend/tests/test_planner_api.py
git commit -m "feat: add orchestrator service and planner api"
```

If git is unavailable, record this task as the fifth local checkpoint.

## Chunk 2: Cutover, Trace, Frontend, Cleanup

### Task 6: Cut ConversationService over to orchestrator

**Files:**
- Modify: `backend/app/services/conversation_service.py`
- Modify: `backend/app/schemas/conversation.py`
- Modify: `backend/app/api/conversations.py`
- Test: `backend/tests/test_conversation_api.py`

- [ ] **Step 1: Write the failing conversation tests**

Add or update tests that verify:
- `send_message()` calls `OrchestratorService`
- assistant messages store planner-oriented summary fields
- clarify responses still create assistant messages
- answer generation still receives execution summary, recent messages, and session state

- [ ] **Step 2: Run the conversation tests to verify they fail**

Run: `cd /home/akalaopaoer/code/crypto-agent/backend && pytest tests/test_conversation_api.py -v`
Expected: FAIL with outdated router-based assumptions

- [ ] **Step 3: Implement the conversation cutover**

Implementation notes:
- Replace `router_service` dependency with `orchestrator_service`.
- Rename `route_summary` to `plan_summary` or `orchestration_summary`.
- Keep transcript persistence format stable where possible, but remove router naming from new writes.

- [ ] **Step 4: Run the conversation tests to verify they pass**

Run: `cd /home/akalaopaoer/code/crypto-agent/backend && pytest tests/test_conversation_api.py -v`
Expected: PASS

- [ ] **Step 5: Local checkpoint**

If git is available:

```bash
git add backend/app/services/conversation_service.py backend/app/schemas/conversation.py backend/app/api/conversations.py backend/tests/test_conversation_api.py
git commit -m "refactor: route conversations through orchestrator"
```

If git is unavailable, record this task as the sixth local checkpoint.

### Task 7: Replace trace payload and trace viewer assumptions

**Files:**
- Modify: `backend/app/services/trace_log_service.py`
- Modify: `backend/tests/test_trace_log.py`
- Modify: `backend/tests/test_trace_api.py`
- Modify: `frontend/app/traces/page.tsx`

- [ ] **Step 1: Write the failing trace tests**

Add or update tests that verify:
- new traces write `plan` or `orchestration` instead of `route`
- new events use `planner.*`, `executor.*`, `summary.*`
- trace API still returns historical traces in a readable form

- [ ] **Step 2: Run the trace tests to verify they fail**

Run: `cd /home/akalaopaoer/code/crypto-agent/backend && pytest tests/test_trace_log.py tests/test_trace_api.py -v`
Expected: FAIL with old route-based assertions

- [ ] **Step 3: Implement trace write/read changes and frontend trace rendering updates**

Implementation notes:
- Keep historical trace compatibility in the read path if feasible.
- Update the traces page to render planner fields without breaking the page shell.

- [ ] **Step 4: Run the trace tests to verify they pass**

Run: `cd /home/akalaopaoer/code/crypto-agent/backend && pytest tests/test_trace_log.py tests/test_trace_api.py -v`
Expected: PASS

- [ ] **Step 5: Local checkpoint**

If git is available:

```bash
git add backend/app/services/trace_log_service.py backend/tests/test_trace_log.py backend/tests/test_trace_api.py frontend/app/traces/page.tsx
git commit -m "refactor: switch traces to planner semantics"
```

If git is unavailable, record this task as the seventh local checkpoint.

### Task 8: Cut frontend chat and API client over to planner naming

**Files:**
- Modify: `frontend/lib/api.ts`
- Rename/Modify: `frontend/components/router-chat.tsx`
- Modify: `frontend/components/dashboard-client.tsx`
- Modify: `frontend/components/conversation-panel.tsx`

- [ ] **Step 1: Write down the failing TypeScript surface**

List all router-named exports/usages to remove:
- `executeRouterQuery`
- `RouterExecutionResponse`
- `RouterChat`
- router-specific copy in dashboard and conversation panel

- [ ] **Step 2: Run lint or build to capture the failing frontend references**

Run: `cd /home/akalaopaoer/code/crypto-agent/frontend && npm run lint`
Expected: FAIL after backend response and type changes introduce outdated router references

- [ ] **Step 3: Implement frontend cutover**

Implementation notes:
- Rename the chat component to `PlannerChat` or `AgentChat`.
- Update API client types and endpoint paths to `/api/planner/execute`.
- Replace all router wording in user-facing copy.
- Keep the current page layout intact.

- [ ] **Step 4: Run frontend lint to verify it passes**

Run: `cd /home/akalaopaoer/code/crypto-agent/frontend && npm run lint`
Expected: PASS

- [ ] **Step 5: Local checkpoint**

If git is available:

```bash
git add frontend/lib/api.ts frontend/components/router-chat.tsx frontend/components/dashboard-client.tsx frontend/components/conversation-panel.tsx
git commit -m "refactor: remove router naming from frontend chat"
```

If git is unavailable, record this task as the eighth local checkpoint.

### Task 9: Remove router modules and obsolete tests

**Files:**
- Delete: `backend/app/services/router_service.py`
- Delete: `backend/app/services/router_llm_service.py`
- Delete: `backend/app/agents/router_agent.py`
- Delete: `backend/app/api/router.py`
- Delete or replace: `backend/tests/test_router_service.py`
- Delete or replace: `backend/tests/test_router_api.py`
- Delete or replace: `backend/tests/test_router_execution.py`
- Delete or replace: `backend/tests/test_router_kline_execution.py`
- Delete or replace: `backend/tests/test_router_binance_execution.py`
- Delete or replace: `backend/tests/test_router_llm_service.py`

- [ ] **Step 1: Replace or remove router-era tests with planner-era coverage**

Make sure equivalent planner coverage exists before deleting each router-specific test file. Avoid deleting assertions without preserving intent in a new planner test.

- [ ] **Step 2: Run the full targeted backend suite before deletion**

Run: `cd /home/akalaopaoer/code/crypto-agent/backend && pytest tests/test_planning_schemas.py tests/test_context_builder.py tests/test_planner.py tests/test_executor.py tests/test_summary_agent.py tests/test_orchestrator_service.py tests/test_planner_api.py tests/test_conversation_api.py tests/test_trace_log.py tests/test_trace_api.py -v`
Expected: PASS

- [ ] **Step 3: Delete router modules and router-only tests**

Implementation notes:
- Remove imports from `main.py`.
- Remove any router compatibility code that survived earlier chunks.
- Ensure no file, event, type, or visible copy still uses router terminology.

- [ ] **Step 4: Re-run the targeted backend suite after deletion**

Run: `cd /home/akalaopaoer/code/crypto-agent/backend && pytest tests/test_planning_schemas.py tests/test_context_builder.py tests/test_planner.py tests/test_executor.py tests/test_summary_agent.py tests/test_orchestrator_service.py tests/test_planner_api.py tests/test_conversation_api.py tests/test_trace_log.py tests/test_trace_api.py -v`
Expected: PASS

- [ ] **Step 5: Local checkpoint**

If git is available:

```bash
git add -A
git commit -m "refactor: remove router modules after planner cutover"
```

If git is unavailable, record this task as the ninth local checkpoint.

### Task 10: Final verification and docs cleanup

**Files:**
- Modify: `README.md`
- Modify: `docs/system-architecture.md`
- Modify any remaining planner/router references found by search

- [ ] **Step 1: Search for leftover router references**

Run: `cd /home/akalaopaoer/code/crypto-agent && rg -n "Router|router\\.|/api/router|RouterChat|executeRouterQuery|RouterExecutionResponse" backend frontend README.md docs`
Expected: only historical docs you intentionally keep, or zero matches in active code paths

- [ ] **Step 2: Update docs and active references**

Update product docs, architecture docs, and active code comments to reflect planner/orchestrator terminology. Do not rewrite historical interview notes unless they are used as active implementation docs.

- [ ] **Step 3: Run full project verification**

Run:

```bash
cd /home/akalaopaoer/code/crypto-agent/backend && pytest -q
cd /home/akalaopaoer/code/crypto-agent/frontend && npm run lint
cd /home/akalaopaoer/code/crypto-agent/frontend && npm run build
```

Expected:
- backend tests PASS
- frontend lint PASS
- frontend build PASS

- [ ] **Step 4: Manual smoke check in browser**

Verify:
- `/` loads
- chat creates conversations and returns planner-backed replies
- `/traces` loads new traces
- `/memory` still loads
- watchlist and paper trading widgets still submit

- [ ] **Step 5: Final local checkpoint**

If git is available:

```bash
git add README.md docs/system-architecture.md
git commit -m "docs: update architecture after planner refactor"
```

If git is unavailable, record this task as the final local checkpoint.
