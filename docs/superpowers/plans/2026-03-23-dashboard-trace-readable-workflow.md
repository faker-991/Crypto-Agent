# Dashboard And Readable Trace Workflow Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the homepage chat-first with a GPT-like layout and turn `/traces` into a readable planner-to-agent workflow review instead of a raw event-first debugger.

**Architecture:** Keep the persisted trace JSON unchanged and derive a `readable_workflow` view on the backend from existing `plan`, `task_results`, `execution_summary`, and `events`. Render `/traces` from that derived contract using focused React components, while simplifying the homepage to a conversation sidebar plus a much larger chat panel.

**Tech Stack:** FastAPI, Python, Pydantic models-as-dicts, pytest, Next.js 15, React 19, TypeScript, ESLint

---

## Chunk 1: Backend Readable Workflow Derivation

### Task 1: Build the readable trace formatter with failing backend tests first

**Files:**
- Create: `backend/app/services/readable_trace_formatter.py`
- Create: `backend/tests/test_readable_trace_formatter.py`
- Test: `backend/tests/test_trace_api.py`

- [ ] **Step 1: Write the failing formatter tests for execute, clarify, legacy, and malformed traces**

```python
from app.services.readable_trace_formatter import build_readable_workflow


def test_build_readable_workflow_for_mixed_analysis_trace() -> None:
    payload = {
        "status": "execute",
        "plan": {
            "goal": "Analyze BTC",
            "mode": "multi_task",
            "decision_mode": "mixed_analysis",
            "reasoning_summary": "Need both external research and price structure.",
            "planner_source": "fallback",
            "agents_to_invoke": ["ResearchAgent", "KlineAgent", "SummaryAgent"],
            "tasks": [
                {"task_id": "research-1", "task_type": "research", "title": "Research BTC", "slots": {"asset": "BTC"}, "depends_on": []},
                {"task_id": "kline-1", "task_type": "kline", "title": "Review BTC price action", "slots": {"asset": "BTC", "market_type": "spot", "timeframes": ["4h", "1d"]}, "depends_on": []},
                {"task_id": "summary-1", "task_type": "summary", "title": "Summarize BTC", "slots": {"asset": "BTC"}, "depends_on": ["research-1", "kline-1"]},
            ],
        },
        "task_results": [
            {
                "task_id": "research-1",
                "task_type": "research",
                "agent": "ResearchAgent",
                "status": "success",
                "summary": "BTC remains worth monitoring.",
                "evidence_sufficient": True,
                "missing_information": [],
                "tool_calls": [
                    {"tool": "search_web", "input": {"query": "BTC crypto tokenomics roadmap catalysts risks"}},
                    {"tool": "fetch_page", "input": {"url": "https://example.com/btc-report"}, "output": {"title": "BTC report"}},
                ],
                "payload": {
                    "asset": "BTC",
                    "bull_case": ["Institutional demand remains durable."],
                    "bear_case": ["Macro tightening can cap upside."],
                    "risks": ["ETF flows can reverse quickly."],
                    "market_context": {"market_cap": 100},
                    "protocol_context": {"category": "store of value"},
                },
            },
            {
                "task_id": "kline-1",
                "task_type": "kline",
                "agent": "KlineAgent",
                "status": "insufficient",
                "summary": "BTC spot market view. 4h: trend intact. 1d: data incomplete.",
                "evidence_sufficient": False,
                "missing_information": ["Indicator coverage incomplete for 1d: rsi"],
                "tool_calls": [
                    {"tool": "get_klines", "timeframe": "4h", "output": {"source": "binance", "market_type": "spot", "candles": 200}},
                    {"tool": "compute_indicators", "timeframe": "1d", "output": {"status": "partial", "missing_indicators": ["rsi"]}},
                ],
                "payload": {
                    "asset": "BTC",
                    "market_type": "spot",
                    "timeframes": ["4h", "1d"],
                    "analyses": {
                        "4h": {"conclusion": "Trend intact."},
                        "1d": {"conclusion": "Data incomplete."},
                    },
                    "market_summary": {"market_type": "spot", "timeframes": ["4h", "1d"], "analysis_summary": "4h intact; 1d incomplete"},
                    "indicator_snapshots": {"1d": {"status": "partial", "missing_indicators": ["rsi"]}},
                    "kline_provenance": {
                        "4h": {"source": "binance", "market_type": "spot", "endpoint_summary": {"endpoint": "klines", "url": "https://api.binance.com/api/v3/klines"}},
                        "1d": {"source": "binance", "market_type": "spot", "endpoint_summary": {"endpoint": "klines", "url": "https://api.binance.com/api/v3/klines"}, "degraded_reason": "indicator coverage incomplete"},
                    },
                },
            },
            {
                "task_id": "summary-1",
                "task_type": "summary",
                "agent": "SummaryAgent",
                "status": "insufficient",
                "summary": "BTC combined summary",
                "evidence_sufficient": False,
                "missing_information": ["Indicator coverage incomplete for 1d: rsi"],
                "payload": {
                    "asset": "BTC",
                    "final_answer": "BTC trend is constructive but 1d evidence is incomplete.",
                    "execution_summary": {
                        "asset": "BTC",
                        "summary": "BTC trend is constructive but 1d evidence is incomplete.",
                        "missing_information": ["Indicator coverage incomplete for 1d: rsi"],
                        "agent_sufficiency": {"ResearchAgent": True, "KlineAgent": False},
                        "provenance": {"degraded_reason": "indicator coverage incomplete"},
                    },
                },
            },
        ],
        "execution_summary": {
            "asset": "BTC",
            "summary": "BTC trend is constructive but 1d evidence is incomplete.",
            "missing_information": ["Indicator coverage incomplete for 1d: rsi"],
            "agent_sufficiency": {"ResearchAgent": True, "KlineAgent": False},
            "provenance": {"degraded_reason": "indicator coverage incomplete"},
        },
        "final_answer": "BTC trend is constructive but 1d evidence is incomplete.",
    }

    workflow = build_readable_workflow(payload)

    assert workflow["final_conclusion"]["final_answer"] == "BTC trend is constructive but 1d evidence is incomplete."
    assert workflow["final_conclusion"]["summary"] == "BTC trend is constructive but 1d evidence is incomplete."
    assert workflow["final_conclusion"]["evidence_sufficient"] is False
    assert workflow["timeline"][0]["kind"] == "planner"
    assert workflow["timeline"][1]["kind"] == "research"
    assert "BTC crypto tokenomics roadmap catalysts risks" in workflow["timeline"][1]["actual_calls"][0]
    assert workflow["timeline"][2]["kind"] == "kline"
    assert "4h, 1d" in " ".join(workflow["timeline"][2]["did"])
    assert workflow["timeline"][3]["kind"] == "summary"


def test_build_readable_workflow_summary_falls_back_to_task_summaries() -> None:
    payload = {
        "status": "execute",
        "plan": {"goal": "Analyze BTC", "mode": "single_task", "needs_clarification": False, "tasks": []},
        "task_results": [],
        "execution_summary": {"task_summaries": ["Research says demand is stable.", "Kline says 4h trend is intact."]},
        "final_answer": None,
    }

    workflow = build_readable_workflow(payload)

    assert workflow["final_conclusion"]["summary"] == "Research says demand is stable. Kline says 4h trend is intact."


def test_build_readable_workflow_for_clarify_trace() -> None:
    payload = {
        "status": "clarify",
        "plan": {
            "goal": "Clarify the asset",
            "mode": "single_task",
            "decision_mode": "clarify",
            "needs_clarification": True,
            "clarification_question": "你想看哪个标的，是现货还是合约？",
            "planner_source": "fallback",
            "agents_to_invoke": [],
            "tasks": [],
        },
        "task_results": [],
        "execution_summary": None,
        "final_answer": "你想看哪个标的，是现货还是合约？",
    }

    workflow = build_readable_workflow(payload)

    assert workflow["final_conclusion"] is None
    assert len(workflow["timeline"]) == 1
    assert workflow["timeline"][0]["kind"] == "planner"
    assert "你想看哪个标的，是现货还是合约？" in " ".join(workflow["timeline"][0]["conclusion"])


def test_build_readable_workflow_for_legacy_route_trace() -> None:
    payload = {
        "route": {"type": "clarify", "agent": "RouterAgent"},
        "status": "clarify",
        "user_query": "看下 4h",
        "task_results": [],
        "execution_summary": None,
        "events": [],
    }

    workflow = build_readable_workflow(payload)

    assert workflow["timeline"][0]["kind"] == "planner"
    assert workflow["timeline"][0]["meta"]["legacy"] is True
    assert "RouterAgent" in " ".join(workflow["timeline"][0]["found"])


def test_build_readable_workflow_ignores_malformed_tool_calls() -> None:
    payload = {
        "status": "execute",
        "plan": {"goal": "Analyze BTC", "mode": "single_task", "needs_clarification": False, "tasks": []},
        "task_results": [
            {
                "task_id": "research-1",
                "task_type": "research",
                "agent": "ResearchAgent",
                "status": "success",
                "summary": "BTC remains worth monitoring.",
                "tool_calls": ["bad", 123, None],
                "payload": {"asset": "BTC"},
            }
        ],
        "execution_summary": {"asset": "BTC"},
        "final_answer": "BTC remains worth monitoring.",
    }

    workflow = build_readable_workflow(payload)

    assert workflow["timeline"][1]["kind"] == "research"
    assert workflow["timeline"][1]["actual_calls"] == ["No structured call details captured."]
```

- [ ] **Step 2: Run the new formatter tests and verify they fail for missing implementation**

Run: `pytest backend/tests/test_readable_trace_formatter.py -v`

Expected: FAIL with `ModuleNotFoundError` or missing `build_readable_workflow`

- [ ] **Step 3: Implement the formatter as a pure backend helper**

```python
def build_readable_workflow(payload: dict) -> dict | None:
    plan = payload.get("plan")
    task_results = payload.get("task_results")
    execution_summary = payload.get("execution_summary")
    final_answer = payload.get("final_answer")

    timeline = []
    planner_stage = _build_planner_stage(payload)
    if planner_stage:
        timeline.append(planner_stage)

    grouped_results = _group_task_results(task_results)
    for stage in grouped_results:
        timeline.append(_build_agent_stage(stage))

    final_conclusion = _build_final_conclusion(
        payload.get("status"),
        execution_summary,
        final_answer,
        grouped_results,
    )
    if not timeline and not final_conclusion:
        return None
    return {"final_conclusion": final_conclusion, "timeline": timeline}
```

Implementation rules:

- keep the module pure and independent from FastAPI
- group task results by `task_type`
- emit grouped stages in this exact order: `research`, `kline`, `summary`, then unknown task types
- always emit human-readable arrays for `did`, `actual_calls`, `found`, and `conclusion`
- derive planner content from `plan` when present, otherwise from `legacy_route`
- accept either `legacy_route` or raw persisted `route` for legacy traces, both shaped like `{"type": "...", "agent": "..."}`, and mark planner metadata with `{"legacy": True}`
- derive `final_conclusion.summary` from `execution_summary.summary`, then joined `execution_summary.task_summaries`, then `final_answer`
- tolerate malformed `task_results` and malformed `tool_calls`
- deduplicate repeated lines while preserving order

- [ ] **Step 4: Run formatter tests until they pass**

Run: `pytest backend/tests/test_readable_trace_formatter.py -v`

Expected: PASS for execute, clarify, legacy, and malformed-trace cases

- [ ] **Step 5: Commit the formatter work**

```bash
# Skip in the current workspace if `.git` is unavailable.
git add backend/app/services/readable_trace_formatter.py
git add backend/tests/test_readable_trace_formatter.py
git commit -m "feat: derive readable workflow traces"
```

### Task 2: Wire the formatter into the trace API and lock the response shape

**Files:**
- Modify: `backend/app/api/trace.py`
- Modify: `backend/tests/test_trace_api.py`
- Test: `backend/tests/test_trace_log.py`

- [ ] **Step 1: Extend API tests to expect `readable_workflow`**

```python
def test_trace_api_reads_one_trace_with_readable_workflow(tmp_path: Path) -> None:
    service = TraceLogService(memory_root=tmp_path)
    path = service.write_trace(
        user_query="帮我看看 BTC",
        status="clarify",
        plan={"goal": "clarify BTC", "mode": "single_task", "needs_clarification": True, "clarification_question": "你想看哪个标的？", "tasks": []},
        task_results=[],
        execution_summary=None,
        events=[],
    )

    payload = read_trace(Path(path).name, service)

    assert "readable_workflow" in payload
    assert payload["plan"]["goal"] == "clarify BTC"
    assert payload["events"] == []
    assert payload["readable_workflow"]["final_conclusion"] is None
    assert payload["readable_workflow"]["timeline"][0]["kind"] == "planner"
    assert payload["readable_workflow"]["timeline"][0]["status"] in {"success", "unknown"}


def test_trace_api_omits_readable_workflow_when_derivation_returns_none(tmp_path: Path) -> None:
    service = TraceLogService(memory_root=tmp_path)
    path = service.write_trace(
        user_query="空 trace",
        status="execute",
        plan=None,
        task_results=[],
        execution_summary=None,
        events=[{"name": "planner.context_built", "actor": "ContextBuilder", "detail": {}}],
    )

    payload = read_trace(Path(path).name, service)

    assert payload["user_query"] == "空 trace"
    assert "readable_workflow" not in payload
    assert payload["events"][0]["name"] == "planner.context_built"
```

- [ ] **Step 2: Run the trace API tests and verify they fail on the missing field**

Run: `pytest backend/tests/test_trace_api.py -v`

Expected: FAIL because `readable_workflow` is absent

- [ ] **Step 3: Import the formatter and attach the derived field in `read_trace`**

```python
from app.services.readable_trace_formatter import build_readable_workflow


@router.get("/{trace_id}")
def read_trace(trace_id: str, trace_log_service: TraceLogService = Depends(get_trace_log_service)) -> dict:
    payload = trace_log_service.read_trace(trace_id)
    payload["events"] = [_normalize_event(event) for event in payload.get("events", [])]
    readable_workflow = build_readable_workflow(payload)
    if readable_workflow is not None:
        payload["readable_workflow"] = readable_workflow
    return payload
```

- [ ] **Step 4: Run the trace API and trace log tests**

Run: `pytest backend/tests/test_trace_api.py backend/tests/test_trace_log.py -v`

Expected: PASS with existing trace listing behavior intact and new readable field present on detail reads

- [ ] **Step 5: Commit the API integration**

```bash
# Skip in the current workspace if `.git` is unavailable.
git add backend/app/api/trace.py
git add backend/tests/test_trace_api.py
git commit -m "feat: expose readable workflow on trace api"
```

## Chunk 2: Trace Page Readable Workflow UI

### Task 3: Extend frontend trace types before changing the page

**Files:**
- Modify: `frontend/lib/api.ts`
- Create: `frontend/components/trace-readable-workflow.tsx`
- Create: `frontend/components/trace-raw-events.tsx`

- [ ] **Step 1: Add the readable workflow types to `frontend/lib/api.ts`**

```ts
export type ReadableWorkflowStage = {
  kind: "planner" | "research" | "kline" | "summary" | "unknown";
  title: string;
  status: "success" | "insufficient" | "failed" | "skipped" | "unknown";
  did: string[];
  actual_calls: string[];
  found: string[];
  conclusion: string[];
  meta: Record<string, unknown>;
};

export type ReadableWorkflow = {
  final_conclusion?: {
    status: "execute" | "clarify" | "failed" | "unknown";
    final_answer?: string | null;
    summary?: string | null;
    evidence_sufficient?: boolean | null;
    missing_information: string[];
    degraded_reason?: string | null;
  } | null;
  timeline: ReadableWorkflowStage[];
};
```

- [ ] **Step 2: Add the new field to `TracePayload` and stub the UI components**

```ts
export type TracePayload = {
  ...
  readable_workflow?: ReadableWorkflow | null;
};
```

Component stubs should accept typed props only and render placeholder headings so the page can be rewired incrementally.

- [ ] **Step 3: Run frontend lint to catch type and import errors early**

Run: `npm run lint`
Workdir: `frontend`

Expected: PASS or only fail on the not-yet-wired placeholder components that will be fixed in the next task

- [ ] **Step 4: Commit the type scaffolding**

```bash
# Skip in the current workspace if `.git` is unavailable.
git add frontend/lib/api.ts
git add frontend/components/trace-readable-workflow.tsx
git add frontend/components/trace-raw-events.tsx
git commit -m "refactor: add readable trace workflow types"
```

### Task 4: Rebuild `/traces` around final conclusion, workflow timeline, and raw trace fallback

**Files:**
- Modify: `frontend/app/traces/page.tsx`
- Modify: `frontend/components/trace-readable-workflow.tsx`
- Modify: `frontend/components/trace-raw-events.tsx`

- [ ] **Step 1: Replace the event-first layout with workflow-first rendering**

Implement the page in this order:

- top section: final conclusion
- middle section: planner and agent timeline cards
- bottom section: raw trace collapse/fallback

The left trace index stays intact.

- [ ] **Step 2: Implement the readable workflow components**

```tsx
export function TraceReadableWorkflow({ workflow }: { workflow: ReadableWorkflow | null | undefined }) {
  if (!workflow) {
    return null;
  }

  return (
    <section className="space-y-5">
      {workflow.final_conclusion ? <FinalConclusionCard conclusion={workflow.final_conclusion} /> : null}
      <WorkflowTimeline stages={workflow.timeline} />
    </section>
  );
}
```

Implementation notes:

- render cards in timeline order received from the backend
- keep the four repeated subsections visible: `Did`, `Actual Calls`, `Found`, `Conclusion`
- hide empty subsections rather than showing empty cards
- make degraded and insufficient states visually obvious
- do not surface raw `task_id` as user-facing text

- [ ] **Step 3: Move existing raw event rendering into `trace-raw-events.tsx`**

Keep the current low-level detail rendering available, but visually secondary.

Suggested API:

```tsx
export function TraceRawEvents({ events }: { events: PlannerEvent[] }) {
  return (
    <details className="rounded-[1.5rem] border border-black/10 bg-white/70 p-5">
      <summary className="cursor-pointer text-sm font-semibold text-black">Raw Trace</summary>
      {/* existing event list rendering moved here */}
    </details>
  );
}
```

- [ ] **Step 4: Run frontend lint and build**

Run: `npm run lint`
Workdir: `frontend`

Expected: PASS

Run: `npm run build`
Workdir: `frontend`

Expected: PASS with `/traces` statically compiling

- [ ] **Step 5: Manual verify an existing trace in the browser**

Run: `npm run dev`
Workdir: `frontend`

Check:

- `/traces?trace=<existing-trace-id>` shows final conclusion above the workflow
- timeline order is `Planner -> ResearchAgent -> KlineAgent -> SummaryAgent` when those stages exist
- cards show real queries, URLs, timeframes, indicators, and summaries
- `Raw Trace` still exposes normalized low-level events

- [ ] **Step 6: Commit the traces UI**

```bash
# Skip in the current workspace if `.git` is unavailable.
git add frontend/app/traces/page.tsx
git add frontend/components/trace-readable-workflow.tsx
git add frontend/components/trace-raw-events.tsx
git commit -m "feat: render readable workflow on traces page"
```

## Chunk 3: Homepage Chat-First Layout

### Task 5: Remove non-chat dashboard dependencies from the homepage entry path

**Files:**
- Modify: `frontend/app/page.tsx`
- Modify: `frontend/components/dashboard-client.tsx`

- [ ] **Step 1: Remove watchlist and portfolio fetching from the page entry**

```tsx
import { DashboardClient } from "../components/dashboard-client";

export default function DashboardPage() {
  return <DashboardClient />;
}
```

- [ ] **Step 2: Strip `DashboardClient` down to a chat-shell wrapper**

```tsx
export function DashboardClient() {
  return (
    <main className="min-h-[calc(100vh-10rem)]">
      <PlannerChat />
    </main>
  );
}
```

Remove:

- watchlist state
- paper trade state
- form submit handlers
- status card rendering
- imports that are no longer used

- [ ] **Step 3: Run frontend lint to catch dead imports and prop mismatches**

Run: `npm run lint`
Workdir: `frontend`

Expected: PASS

- [ ] **Step 4: Commit homepage entry cleanup**

```bash
# Skip in the current workspace if `.git` is unavailable.
git add frontend/app/page.tsx
git add frontend/components/dashboard-client.tsx
git commit -m "refactor: make dashboard homepage chat first"
```

### Task 6: Resize the planner chat into a GPT-like layout and remove extra dashboard clutter

**Files:**
- Modify: `frontend/components/planner-chat.tsx`
- Modify: `frontend/components/conversation-sidebar.tsx`
- Modify: `frontend/components/conversation-panel.tsx`

- [ ] **Step 1: Tighten the sidebar and enlarge the conversation panel**

Target changes:

- make the sidebar visibly narrower than the main panel
- remove the extra “Flow” card
- let the conversation panel take most horizontal space
- increase visible message area height
- make the composer feel larger and more central

Suggested layout ratios:

```tsx
<div className="mt-6 grid gap-4 xl:grid-cols-[0.28fr_0.72fr]">
```

Use the exact ratio that best fits the current composition after implementation, but keep the sidebar clearly secondary.

- [ ] **Step 2: Update the conversation panel proportions and copy**

```tsx
<div className="min-h-[70vh] overflow-hidden rounded-[2rem] ...">
  <div className="flex-1 overflow-y-auto ...">{/* messages */}</div>
  <form className="...">
    <textarea className="min-h-36 ..." />
  </form>
</div>
```

Implementation notes:

- keep `Open Trace` links
- keep starter prompts if they still fit above the grid
- ensure mobile stacks sidebar above panel cleanly
- avoid introducing a second informational side rail on the homepage

- [ ] **Step 3: Run frontend lint and build**

Run: `npm run lint`
Workdir: `frontend`

Expected: PASS

Run: `npm run build`
Workdir: `frontend`

Expected: PASS with the homepage compiling cleanly

- [ ] **Step 4: Manual verify homepage behavior**

Run: `npm run dev`
Workdir: `frontend`

Check:

- `/` shows only the conversation sidebar and the larger chat panel
- watchlist, paper trade, paper portfolio, and status cards are gone
- the chat composer is larger than before
- mobile stacks the sidebar above the panel without overflow

- [ ] **Step 5: Commit the layout changes**

```bash
# Skip in the current workspace if `.git` is unavailable.
git add frontend/components/planner-chat.tsx
git add frontend/components/conversation-sidebar.tsx
git add frontend/components/conversation-panel.tsx
git commit -m "feat: adopt gpt-like dashboard chat layout"
```

## Execution Notes

- Prefer implementing Chunk 1 completely before touching the frontend, because the trace UI should consume a stable backend contract.
- Do not add a new frontend test framework in this task; use the existing backend pytest coverage plus frontend lint/build/manual verification.
- If `frontend/app/traces/page.tsx` becomes hard to reason about, keep page-level data loading in the page and move presentational detail into the dedicated workflow and raw-event components above.
- If `.git` is still unavailable when executing the plan, skip commit steps and record that explicitly in the execution summary.
