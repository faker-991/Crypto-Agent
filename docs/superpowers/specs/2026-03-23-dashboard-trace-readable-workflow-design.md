# Dashboard Chat Layout And Readable Trace Workflow Design

Date: 2026-03-23

## Context

The current dashboard homepage mixes chat, watchlist, paper portfolio, paper trade input, and status cards in a split layout. This makes the conversation surface feel secondary even though the dashboard is now primarily used as the entry point for multi-turn planner-backed chat.

The current trace detail page also exposes raw execution events and summary tiles, but it does not answer the practical questions a user asks when reviewing a run:

- What did the planner decide to do?
- Why was that plan chosen?
- Which agents were called?
- What did each agent actually query or compute?
- What evidence did each agent find?
- What was insufficient or degraded?
- What final summary did the system produce?

The existing trace payload already contains most of this information in `plan`, `task_results`, `execution_summary`, and `tool_calls`, but the frontend surfaces it as low-level fields and event fragments rather than a readable workflow.

## User-Approved Direction

The user approved the following design decisions during brainstorming:

- Homepage should remove watchlist, paper portfolio, paper trade, and status cards.
- Homepage layout should follow a GPT-like composition:
  - smaller conversation sidebar on the left
  - much larger chat panel on the right
- The readable end-to-end workflow view should be added only to `/traces`.
- The trace review should prioritize practical execution detail over internal ids.

## Goals

- Make the homepage feel like a chat-first workspace.
- Keep the conversation sidebar visible but visually secondary.
- Turn trace detail into a readable execution story rather than a raw event dump.
- Show actual planner and agent work:
  - planner reasoning and task plan
  - agents invoked and their role
  - search queries, fetched URLs, K-line timeframes, indicators, and summary outputs
  - missing evidence and degraded conditions
- Preserve raw trace fidelity for debugging without making it the primary UI.

## Non-Goals

- No redesign of `/memory`, `/assets`, or other non-dashboard pages.
- No change to the conversation message UI beyond the homepage layout resize.
- No new trace-writing format on disk for this iteration.
- No duplication of the readable workflow inside chat messages.

## Chosen Architecture

The implementation should use a hybrid approach:

- Keep the persisted trace JSON unchanged.
- Add a lightweight derived `readable_workflow` view to the trace read path.
- Render `/traces` primarily from that derived structure.
- Keep raw `events` available as a secondary collapsible section for debugging.

This avoids a heavy trace storage refactor while preventing the frontend from reimplementing too much trace parsing logic.

## Homepage Design

### Layout

The homepage should become a chat-first page composed of:

- a narrow conversation sidebar
- a wide conversation panel

The surrounding dashboard container can keep the current visual language, but the layout should remove all non-chat cards. The conversation panel should occupy substantially more width than it does now.

### Component Scope

`frontend/components/dashboard-client.tsx`

- Remove watchlist, portfolio, paper trade, and status rendering from the homepage.
- Remove related local form state and mutation handlers that are no longer used on the page.
- Render only the planner chat surface.

`frontend/components/planner-chat.tsx`

- Keep the starter prompts if they still fit the layout.
- Shift the main grid ratio closer to a GPT-like chat workspace.
- Treat the sidebar as secondary navigation and the conversation panel as the main surface.
- Remove the extra “Flow” card because `/traces` becomes the detailed execution review surface.

`frontend/components/conversation-sidebar.tsx`

- Keep persistent session switching.
- Make the sidebar visually smaller and denser.

`frontend/components/conversation-panel.tsx`

- Increase the usable chat area and composer presence.
- Keep `Open Trace` links on assistant messages.
- Do not add the full readable workflow here.

## Trace Detail Design

### High-Level Page Order

The trace detail page should be reorganized into three primary sections:

1. Final conclusion
2. Readable workflow timeline
3. Raw trace details

This order optimizes for how users actually review a run: first the answer, then how the system arrived there, then low-level debugging data if needed.

### Final Conclusion Section

This section should present:

- `final_answer`
- key conclusion summary
- evidence sufficiency / missing information
- degraded reason if present

This should replace the current experience where a user has to infer the real outcome from tiles and event fragments.

### Readable Workflow Timeline

The timeline should render one card per workflow stage in the following order when present:

- Planner
- ResearchAgent
- KlineAgent
- SummaryAgent

The cards should be derived from `plan` plus `task_results`, not from raw event names.

Each card should use the same four readable subsections:

1. `Did`
2. `Actual Calls`
3. `Found`
4. `Conclusion`

### Planner Card

The planner card should surface:

- why the planner chose the path:
  - `goal`
  - `decision_mode`
  - `reasoning_summary`
  - `planner_source`
- what it planned:
  - task titles
  - task order
  - humanized dependency description instead of raw task ids
- which agents it prepared to invoke:
  - `agents_to_invoke`
  - plain-language responsibility description for each agent
- final planning path:
  - for example, “mixed analysis: research, then kline, then summary”

The planner card must not foreground `task_id`.

### ResearchAgent Card

The research card should surface actual research work from `task_results[*].tool_calls` and payload:

- search queries used
- fetched URLs and page titles
- market context found
- protocol context found
- bull case
- bear case
- risks
- missing information
- evidence sufficiency

### KlineAgent Card

The kline card should surface:

- asset and market type
- timeframes analyzed
- data source and endpoint by timeframe
- indicator computation status
- missing indicators
- timeframe conclusions
- market summary
- degraded reasons or missing data

Raw candle arrays should never be rendered in the main readable card.

### SummaryAgent Card

The summary card should surface:

- which upstream agent outputs were combined
- combined task summaries
- final synthesized answer
- agent sufficiency
- missing information

It should explain which conclusion came from prior agent work rather than only restating a final sentence.

### Raw Trace Section

The existing event-driven trace detail should be preserved under a collapsed or visually secondary `Raw Trace` section for debugging and regression triage.

## Derived API Shape

The trace read response should gain a derived field such as:

- `readable_workflow`

### Response Contract

`readable_workflow` is optional at the top level. If derivation fails entirely, the trace response should still return raw fields and the frontend should fall back to the existing raw-trace presentation.

When present, `readable_workflow` should follow this shape:

```json
{
  "final_conclusion": {
    "status": "execute",
    "final_answer": "...",
    "summary": "...",
    "evidence_sufficient": true,
    "missing_information": [],
    "degraded_reason": null
  },
  "timeline": [
    {
      "kind": "planner",
      "title": "Planner",
      "status": "success",
      "did": [],
      "actual_calls": [],
      "found": [],
      "conclusion": [],
      "meta": {}
    }
  ]
}
```

Field expectations:

- `final_conclusion`
  - optional when the trace never executed beyond clarification or when no conclusion can be derived
  - `status` is one of `execute`, `clarify`, `failed`, or `unknown`
  - `summary` is a short human-readable synthesis derived from `execution_summary.summary`, `execution_summary.task_summaries`, or `final_answer`, in that order of preference
  - `evidence_sufficient` is derived from summary payloads when present; otherwise null is allowed
  - `missing_information` is always an array
  - `degraded_reason` is null when not present
- `timeline`
  - always an array when `readable_workflow` exists
  - each item represents one rendered stage card
  - `kind` is one of `planner`, `research`, `kline`, `summary`, or `unknown`
  - `status` is one of `success`, `insufficient`, `failed`, `skipped`, or `unknown`
  - `did`, `actual_calls`, `found`, and `conclusion` are always arrays of human-readable strings
  - `meta` is an object for compact structured labels such as `market_type`, `timeframes`, or `planner_source`

This field should be derived in the backend trace read path from existing persisted trace content. It should not replace the original fields.

### Timeline Grouping Rules

The formatter must build timeline cards using deterministic rules:

- Always render at most one planner card.
- Render the planner card first when either `plan` or `legacy_route` is present.
- Group task results by `task_type`, not by `task_id`.
- Collapse multiple tasks of the same `task_type` into one card in execution order.
- Within a grouped card:
  - append `did`, `actual_calls`, `found`, and `conclusion` content in original task order
  - deduplicate identical human-readable lines
- Render grouped cards in this order when present:
  - `research`
  - `kline`
  - `summary`
- If an unknown task type is encountered, render it as `kind: "unknown"` after known stages rather than dropping it.
- If a run is partial:
  - render only the stages that can be derived
  - do not synthesize missing stages
- If a run is clarify-only:
  - render a planner card
  - omit agent cards
  - omit `final_conclusion` unless a readable clarification conclusion can be derived

### Legacy And Malformed Trace Handling

The formatter must degrade explicitly for older or malformed traces:

- If `plan` is missing but `legacy_route` exists:
  - derive a planner card from `legacy_route`
  - mark planner metadata as legacy-derived
- If `task_results` is missing or not an array:
  - render only planner and final conclusion sections that can be derived
- If a `task_result` entry is malformed:
  - skip invalid structured extraction for that entry
  - add a readable note such as `Structured task detail was unavailable for one stage.`
- If `tool_calls` is missing, not an array, or contains non-object items:
  - ignore malformed items
  - surface `No structured call details captured.` when no usable call detail remains
- If `execution_summary` is missing or malformed:
  - derive conclusion text from `final_answer` if possible
  - otherwise omit `final_conclusion`
- If all derived formatting fails:
  - omit `readable_workflow`
  - keep raw `events` and existing top-level fields intact

## Implementation Notes

### Backend

`backend/app/api/trace.py`

- Enrich trace read responses with a derived readable workflow payload.

`backend/app/services/trace_log_service.py`

- No storage format changes for this iteration.
- Reuse existing trace contents and keep raw events intact.

Optional helper:

- add a dedicated formatter/helper module for building readable workflow payloads so formatting logic does not live directly in the FastAPI route.

### Frontend

`frontend/app/traces/page.tsx`

- Replace the current event-first layout with:
  - conclusion section
  - workflow timeline cards
  - raw trace fallback section
- Prefer human-readable labels and grouped evidence blocks.

`frontend/lib/api.ts`

- extend `TracePayload` with the new derived workflow type.

## Error Handling

- If `plan` is missing, show only the sections that can be derived.
- If a particular agent did not run, omit that stage.
- If tool call detail is missing, show a concise “No structured call details captured.”
- If the trace is degraded, surface the degraded reason in both the conclusion section and the affected agent card.
- If the trace is legacy-derived, label it clearly rather than pretending it came from the current planner format.

## Testing

Backend tests should verify:

- trace read responses include the derived readable workflow field
- planner tasks are humanized without exposing dependency ids as primary text
- research tool calls are converted into readable search/fetch evidence
- kline provenance and indicator status are converted into readable market evidence
- summary task results propagate missing information and sufficiency correctly

Frontend tests or manual verification should verify:

- homepage no longer shows watchlist, portfolio, paper trade, or status cards
- homepage chat surface is visibly larger and sidebar smaller
- homepage keeps a usable mobile layout with the sidebar stacked above the conversation panel
- trace detail renders planner and agent workflow cards in the correct order
- final conclusion appears above the workflow
- raw trace remains available as secondary detail

## Rollout

1. Add backend readable workflow derivation.
2. Update frontend trace types and trace detail rendering.
3. Simplify homepage to chat-first layout.
4. Verify planner, research, kline, and summary traces against real sample data.
