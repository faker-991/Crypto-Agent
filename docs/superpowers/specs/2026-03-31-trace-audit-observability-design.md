# Trace Audit Observability Design

Date: 2026-03-31
Status: Draft approved by user in terminal design review

## Goal

Upgrade the current trace system from a timeline-first engineering log into an audit-first observability surface that can answer:

- What conclusion did the agent produce?
- Which evidence supports that conclusion?
- Which websites and tools were actually used?
- What happened in each ReAct step?
- How many tokens and how much time were consumed?
- Which model callbacks happened, and where did fallback or failure occur?

The design prioritizes execution audit first, then debugging, then product demonstration.

## Current Gaps

The current implementation already persists structured spans and renders a timeline-oriented trace UI, but it still has several audit gaps:

- The frontend does not clearly explain the evidence chain from tool calls to conclusions.
- `search_web` and `fetch_page` activity is visible only as low-level tool spans, not as a human-readable dossier of sources and extracted findings.
- ReAct step data is not rendered as an audit artifact; users cannot clearly see why the agent took each action.
- LLM callback timing is not surfaced in a way that helps explain latency and fallback behavior.
- Old traces and new traces are not normalized to the same audit contract, which causes rendering fragility.

## Non-Goals

This design does not include:

- Full tool re-execution replay
- Approval workflows
- Cryptographic immutability or signature-based compliance controls
- Public-facing reporting exports

These can be built later on top of the normalized audit contract defined here.

## Product Outcome

The trace detail page should let a user answer three questions without reading raw JSON:

1. What was the final answer and was it sufficiently supported?
2. What concrete evidence was collected, from which tools and websites?
3. What exact execution path, cost, and fallback behavior led to that answer?

## Recommended Approach

### Option 1: Timeline-first incremental enhancement

Keep the existing span timeline as the main view and add a few more badges and tabs.

Pros:

- Lowest implementation cost
- Minimal backend changes

Cons:

- Still poor for audit reading
- Users must infer evidence and reasoning from low-level spans

### Option 2: Evidence-first dossier

Make the page mostly about conclusions and evidence, with the execution timeline hidden below.

Pros:

- Best for explaining why the answer is justified

Cons:

- Weaker for runtime debugging and cost review

### Option 3: Hybrid audit dossier and execution cockpit

Render an audit overview at the top, then a conclusion and evidence dossier, then reasoning steps, then the raw execution timeline.

Pros:

- Best match for audit, debugging, and interview demo use cases
- Makes website/tool provenance explicit
- Preserves low-level spans for engineering inspection

Cons:

- Requires a new normalized readable workflow contract

### Recommendation

Use Option 3.

The current project already has spans, metrics, and trace persistence. The missing piece is not raw data collection; it is a stable audit presentation contract that maps execution into conclusions, evidence, steps, and timeline.

## Trace Data Model

The trace payload should continue to persist canonical spans as the source of truth. A formatter layer should derive an audit-oriented readable workflow contract for the frontend.

### Layer 1: Canonical Trace

Persisted in trace JSON. This remains the durable execution record.

Fields already present or to be extended:

- `trace_id`
- `timestamp`
- `status`
- `user_query`
- `plan`
- `task_results`
- `execution_summary`
- `final_answer`
- `spans`
- `metrics_summary`
- `tool_usage_summary`
- `events`

### Layer 2: Audit Readable Workflow

Derived from the canonical trace by a formatter. This is the only contract the frontend should consume for the audit page.

It contains five top-level sections:

- `audit_summary`
- `conclusions`
- `evidence_records`
- `reasoning_steps`
- `timeline`

## Audit Summary Contract

Purpose: top-strip overview for cost, status, and fallback visibility.

Fields:

- `trace_status`
- `started_at`
- `ended_at`
- `duration_ms`
- `prompt_tokens`
- `completion_tokens`
- `total_tokens`
- `llm_calls`
- `tool_calls`
- `failed_calls`
- `degraded_calls`
- `models_used`
- `providers_used`
- `fallback_used`
- `first_failed_span_id`
- `first_failed_step_id`
- `callback_summary`

`callback_summary` contains:

- `started_count`
- `completed_count`
- `failed_count`
- `first_token_latency_ms_avg`
- `finish_reasons`

## Conclusions Contract

Purpose: make final claims explicit and traceable to evidence.

Each conclusion record contains:

- `conclusion_id`
- `kind`
  - `final`
  - `technical`
  - `market`
  - `risk`
  - `catalyst`
  - `sentiment`
- `text`
- `status`
- `summary`
- `missing_information`
- `evidence_ids`
- `derived_from_step_ids`

At minimum there should be one `final` conclusion. Additional typed conclusions can be derived from agent outputs or answer-generation context.

## Evidence Records Contract

Purpose: represent every audit-worthy source and extracted claim in a uniform structure.

Each evidence record contains:

- `evidence_id`
- `type`
  - `technical`
  - `market`
  - `risk`
  - `catalyst`
  - `sentiment`
  - `webpage`
  - `search_result`
  - `derived`
- `title`
- `summary`
- `source_kind`
  - `tool`
  - `llm`
  - `derived`
- `source_tool`
- `source_url`
- `source_domain`
- `source_span_id`
- `captured_at`
- `confidence`
- `attributes`

### Search Evidence

For `search_web`, the formatter should emit:

- one parent evidence record for the search action, including:
  - `query`
  - `provider`
  - `result_count`
- child evidence records for selected or referenced results, including:
  - `title`
  - `url`
  - `domain`
  - `snippet`

### Fetch Evidence

For `fetch_page`, the formatter should emit:

- `url`
- `title`
- `domain`
- `strategy`
- `content_summary`
- `failure_reason`
- `extraction_status`

### Market and Technical Evidence

For `get_ticker`, `get_klines`, and indicator computation, emit evidence records such as:

- timeframe used
- price snapshot summary
- support/resistance summary
- trend regime
- relevant numeric findings

## Reasoning Steps Contract

Purpose: present ReAct reasoning as audit-readable step records without exposing raw chain-of-thought.

Each step record contains:

- `step_id`
- `agent`
- `round_index`
- `decision_summary`
- `action`
- `args`
- `observation_summary`
- `new_evidence_ids`
- `status`
- `duration_ms`
- `llm_span_id`
- `tool_span_id`
- `callback`

`callback` contains:

- `started_at`
- `first_token_at`
- `completed_at`
- `failed_at`
- `finish_reason`
- `error`

The key rule is that `decision_summary` should be a structured action summary, not raw internal thought text.

## Timeline Contract

Purpose: preserve engineering-grade detail for debugging and audit drill-down.

Timeline nodes continue to map to spans and contain:

- `span_id`
- `parent_span_id`
- `kind`
- `name`
- `status`
- `title`
- `summary`
- `start_ts`
- `end_ts`
- `duration_ms`
- `metrics`
- `detail_tabs`

This remains the lowest-level user-facing view, but it is no longer the primary storytelling layer.

## Formatter Responsibilities

The formatter should become responsible for deriving audit semantics from spans.

Responsibilities:

- Normalize old and new trace shapes
- Compute `audit_summary`
- Derive evidence records from tool outputs
- Group LLM and tool spans into reasoning steps
- Link conclusions to evidence ids
- Preserve timeline nodes for low-level inspection

This means the frontend no longer infers business meaning from raw spans.

## Frontend Information Architecture

The trace detail page should adopt a hybrid audit dossier plus execution cockpit layout.

### Section 1: Audit Overview Strip

Displayed first, always visible near the top.

Cards:

- Status
- Duration
- Total Tokens
- LLM Calls
- Tool Calls
- Failures
- Models Used
- Fallback Used

This is the entry point for operational audit and cost review.

### Section 2: Conclusion and Evidence Dossier

Displayed directly under the overview strip. This is the primary reading area.

Layout:

- left column: final conclusion, missing information, degraded reasons
- right column: evidence dossier grouped by type

Evidence groups:

- Technical
- Market
- Risk
- Catalyst
- Sentiment

Each evidence card shows:

- source domain or tool
- title
- one-sentence summary
- capture time
- linked conclusion badges
- click-to-open detail

For web search, the card should explicitly show:

- search query
- search provider
- returned websites
- selected URLs

For page fetch, the card should explicitly show:

- URL
- extraction strategy
- extracted content summary
- failure or fallback path if relevant

### Section 3: Reasoning Steps

Displayed below the dossier.

Each step card shows:

- step number
- agent name
- decision summary
- action and args
- observation summary
- newly added evidence
- token usage
- duration
- callback lifecycle summary

This section answers how the agent arrived at the conclusion step by step.

### Section 4: Execution Timeline

Displayed last.

It keeps the current raw execution navigation with filters such as:

- All
- Failed
- LLM
- Tool
- Research
- Kline

Clicking a node still opens Input, Output, Error, and Audit tabs.

## Interaction Design

To improve observability, the frontend must link the different layers together.

Required interactions:

- Clicking an evidence card highlights the associated timeline node.
- Clicking a conclusion highlights the evidence that supports it.
- Clicking a reasoning step highlights the linked LLM and tool spans.
- If a trace has failures, the page auto-scrolls or selects the first failed span or step by default.
- Search records support a collapsible list of found sites and selected URLs.
- Fetch records support a collapsible list of extraction attempts or strategies.

## Backward Compatibility

Existing traces in local storage will not contain the full new audit contract.

Compatibility rules:

- The formatter must emit empty defaults for missing audit sections.
- The frontend must treat every readable workflow section as optional.
- If evidence or reasoning steps are missing, the page still renders overview, conclusion, and timeline.
- The timeline must not assume `metrics`, `detail_tabs`, `meta`, or `overview` are present.

## Error Handling

The audit UI should degrade gracefully rather than crash.

If trace data is partially missing:

- show available sections
- replace missing sections with empty-state cards
- never let missing derived data break the raw timeline view

If the formatter cannot derive evidence records:

- log the failure in formatter output
- keep the raw timeline visible
- mark the evidence section as unavailable rather than empty

## Testing Strategy

### Backend

Add formatter tests for:

- audit summary derivation
- search evidence derivation
- fetch evidence derivation
- reasoning step derivation
- old trace compatibility
- conclusion-to-evidence linkage

### Frontend

Add component tests or contract tests for:

- overview strip rendering from full and partial audit payloads
- evidence dossier rendering with website sources
- reasoning step cards
- timeline fallback rendering for old traces

### Smoke Tests

Run at least these real scenarios:

1. Research-heavy trace with `search_web` and `fetch_page`
2. Kline-heavy trace with multi-timeframe analysis
3. Mixed trace with fallback and insufficient evidence

For each scenario verify that:

- websites used are visible
- extracted evidence is visible
- conclusions are linked to evidence
- callback and token usage are visible
- raw timeline is still inspectable

## Migration Strategy

Implement in phases:

1. Extend formatter to emit the new audit contract with empty defaults
2. Update frontend to read only the normalized contract
3. Add evidence derivation for search and fetch tools
4. Add reasoning steps and callback summary rendering
5. Retain raw timeline as a fallback-safe section

This sequence minimizes UI breakage while upgrading observability semantics.

## Success Criteria

This work is successful when a user can open a single trace and answer all of the following without reading raw JSON:

- What did the agent conclude?
- Which evidence supports that conclusion?
- Which websites were searched and opened?
- What did each page contribute?
- What did each ReAct step do?
- How many tokens and how much time were consumed?
- Which fallback or callback events occurred?
