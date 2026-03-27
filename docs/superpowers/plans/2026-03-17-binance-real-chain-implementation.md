# Binance Real Chain Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace placeholder market-data behavior with a real Binance `spot + futures` execution chain, then upgrade the asset page, router chat, and traces UI to expose real data and execution provenance.

**Architecture:** Keep the existing FastAPI + Next.js shape, but make Binance the primary market-data source for price, ticker, and kline flows. Build richer trace events around market fetches and analysis, then consume those stable contracts in the asset page, chat UI, and trace timeline.

**Tech Stack:** FastAPI, httpx, pytest, Next.js App Router, React, lightweight-charts, TypeScript

---

## File Map

**Create**

- `backend/tests/test_binance_market_adapter_real_chain.py`
- `backend/tests/test_router_binance_execution.py`
- `backend/tests/test_trace_api_real_chain.py`
- `frontend/components/router-chat.tsx`

**Modify**

- `backend/app/clients/binance_market_adapter.py`
- `backend/app/services/market_data_service.py`
- `backend/app/services/kline_analysis_service.py`
- `backend/app/agents/kline_agent.py`
- `backend/app/services/router_service.py`
- `backend/app/services/trace_log_service.py`
- `backend/app/api/research.py`
- `backend/app/api/router.py`
- `backend/app/api/trace.py`
- `backend/app/schemas/kline.py`
- `backend/app/schemas/execution.py`
- `backend/app/agents/router_agent.py`
- `frontend/lib/api.ts`
- `frontend/app/assets/[symbol]/page.tsx`
- `frontend/app/page.tsx`
- `frontend/components/dashboard-client.tsx`
- `frontend/app/traces/page.tsx`

---

## Chunk 1: Real Binance Data Foundation

### Task 1: Make Binance adapter build real spot and futures requests

**Files:**
- Modify: `backend/app/clients/binance_market_adapter.py`
- Test: `backend/tests/test_binance_market_adapter_real_chain.py`

- [ ] **Step 1: Write the failing adapter tests**

```python
def test_builds_spot_klines_request() -> None:
    ...

def test_builds_futures_klines_request() -> None:
    ...

def test_parses_ticker_response() -> None:
    ...
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest backend/tests/test_binance_market_adapter_real_chain.py -q`
Expected: FAIL because ticker helpers and request coverage do not exist yet.

- [ ] **Step 3: Write minimal implementation**

Add adapter methods for:
- spot/futures ticker fetch
- spot/futures klines fetch
- explicit endpoint metadata for tracing

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest backend/tests/test_binance_market_adapter_real_chain.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/clients/binance_market_adapter.py backend/tests/test_binance_market_adapter_real_chain.py
git commit -m "feat: add real binance spot and futures adapter coverage"
```

### Task 2: Make market data service return real-source metadata

**Files:**
- Modify: `backend/app/services/market_data_service.py`
- Modify: `backend/app/schemas/kline.py`
- Test: `backend/tests/test_market_data_service.py`

- [ ] **Step 1: Write the failing service tests**

Cover:
- real response carries source metadata
- fallback response is marked degraded
- ticker and kline flows keep market type explicit

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest backend/tests/test_market_data_service.py -q`
Expected: FAIL because service only returns candles and silently falls back.

- [ ] **Step 3: Write minimal implementation**

Refactor service to return structured results containing:
- candles
- ticker summary
- source: `binance` or `fallback`
- endpoint summary
- degraded reason when fallback is used

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest backend/tests/test_market_data_service.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/market_data_service.py backend/app/schemas/kline.py backend/tests/test_market_data_service.py
git commit -m "feat: return market data source metadata and fallback markers"
```

---

## Chunk 2: Analysis And Router Real-Data Execution

### Task 3: Base kline analysis on structured real market payloads

**Files:**
- Modify: `backend/app/services/kline_analysis_service.py`
- Modify: `backend/app/agents/kline_agent.py`
- Test: `backend/tests/test_kline_agent.py`

- [ ] **Step 1: Write the failing kline agent tests**

Cover:
- spot and futures analysis keeps market type
- analysis stores source metadata
- asset memory writeback keeps technical data without erasing prior research fields

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest backend/tests/test_kline_agent.py -q`
Expected: FAIL because kline execution does not preserve source/provenance fields yet.

- [ ] **Step 3: Write minimal implementation**

Make `KlineAgent` consume the richer market-data payload and persist:
- market type
- source
- endpoint summary
- degraded flag

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest backend/tests/test_kline_agent.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/kline_analysis_service.py backend/app/agents/kline_agent.py backend/tests/test_kline_agent.py
git commit -m "feat: preserve real market provenance in kline analysis"
```

### Task 4: Route Binance-related questions through the real data chain

**Files:**
- Modify: `backend/app/agents/router_agent.py`
- Modify: `backend/app/services/router_service.py`
- Modify: `backend/app/api/router.py`
- Test: `backend/tests/test_router_binance_execution.py`

- [ ] **Step 1: Write the failing router execution tests**

Cover:
- spot price/kline questions execute via Binance-backed path
- futures questions keep `market_type="futures"`
- execution payload includes answer text plus data provenance

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest backend/tests/test_router_binance_execution.py -q`
Expected: FAIL because router currently returns generic research/kline execution without answer-generation contract.

- [ ] **Step 3: Write minimal implementation**

Update router execution so Binance-related requests return:
- human-readable answer
- structured market summary
- trace-friendly provenance metadata

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest backend/tests/test_router_binance_execution.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/agents/router_agent.py backend/app/services/router_service.py backend/app/api/router.py backend/tests/test_router_binance_execution.py
git commit -m "feat: route binance questions through real market execution"
```

---

## Chunk 3: Trace Enrichment

### Task 5: Record Binance endpoint calls in trace events

**Files:**
- Modify: `backend/app/services/trace_log_service.py`
- Modify: `backend/app/schemas/execution.py`
- Modify: `backend/app/api/trace.py`
- Test: `backend/tests/test_trace_api_real_chain.py`

- [ ] **Step 1: Write the failing trace tests**

Cover:
- trace event contains step name
- Binance endpoint name is present
- input parameter summary is present
- output summary is present
- degraded/fallback state is present when used

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest backend/tests/test_trace_api_real_chain.py -q`
Expected: FAIL because current trace payload is too thin.

- [ ] **Step 3: Write minimal implementation**

Expand event detail shape to include:
- `integration`
- `endpoint`
- `input_summary`
- `output_summary`
- `degraded`
- `error`

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest backend/tests/test_trace_api_real_chain.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/trace_log_service.py backend/app/schemas/execution.py backend/app/api/trace.py backend/tests/test_trace_api_real_chain.py
git commit -m "feat: enrich trace events with binance execution metadata"
```

---

## Chunk 4: Asset Page Upgrade

### Task 6: Upgrade asset page to real spot and futures charting

**Files:**
- Modify: `frontend/lib/api.ts`
- Modify: `frontend/app/assets/[symbol]/page.tsx`
- Modify: `frontend/components/kline-chart.tsx`

- [ ] **Step 1: Define the failing UI contract**

Document in code and types that asset page requires:
- market type switch
- provenance metadata
- degraded indicator
- richer analysis summary

- [ ] **Step 2: Run frontend lint before changes**

Run: `cd frontend && npm run lint`
Expected: PASS

- [ ] **Step 3: Write minimal implementation**

Update asset page to show:
- spot/futures switch
- real-data source label
- degraded banner when fallback occurs
- expanded indicator cards around the chart

- [ ] **Step 4: Verify frontend**

Run:
- `cd frontend && npm run lint`
- `curl -s http://127.0.0.1:8000/api/research/...` as needed during manual verification

Expected: lint PASS and page renders in dev mode.

- [ ] **Step 5: Commit**

```bash
git add frontend/lib/api.ts frontend/app/assets/[symbol]/page.tsx frontend/components/kline-chart.tsx
git commit -m "feat: show real binance asset charts with provenance"
```

---

## Chunk 5: Chat UI Upgrade

### Task 7: Replace command console with chat interface

**Files:**
- Create: `frontend/components/router-chat.tsx`
- Modify: `frontend/app/page.tsx`
- Modify: `frontend/components/dashboard-client.tsx`
- Modify: `frontend/lib/api.ts`

- [ ] **Step 1: Define the failing UI contract**

Document that home page now needs:
- message list
- user/assistant turns
- trace link per assistant answer
- structured market summary block

- [ ] **Step 2: Run frontend lint before changes**

Run: `cd frontend && npm run lint`
Expected: PASS

- [ ] **Step 3: Write minimal implementation**

Introduce `router-chat.tsx` and move router interaction into:
- chat messages
- pending state
- answer cards with provenance

Keep existing watchlist and portfolio sections intact.

- [ ] **Step 4: Verify frontend**

Run: `cd frontend && npm run lint`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add frontend/components/router-chat.tsx frontend/app/page.tsx frontend/components/dashboard-client.tsx frontend/lib/api.ts
git commit -m "feat: upgrade router console to real chat interface"
```

---

## Chunk 6: Traces UI Upgrade And Final Verification

### Task 8: Turn traces page into a provenance timeline

**Files:**
- Modify: `frontend/app/traces/page.tsx`
- Modify: `frontend/lib/api.ts`

- [ ] **Step 1: Define the failing UI contract**

Document that traces page must show:
- ordered execution timeline
- Binance endpoint cards
- input summary
- output summary
- degraded marker

- [ ] **Step 2: Run frontend lint before changes**

Run: `cd frontend && npm run lint`
Expected: PASS

- [ ] **Step 3: Write minimal implementation**

Upgrade traces page from raw event list to:
- visual timeline
- integration cards
- degraded/error badges

- [ ] **Step 4: Verify frontend**

Run: `cd frontend && npm run lint`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add frontend/app/traces/page.tsx frontend/lib/api.ts
git commit -m "feat: visualize binance execution provenance in traces"
```

### Task 9: Final verification for phase 1

**Files:**
- Review only: backend and frontend files touched above

- [ ] **Step 1: Run backend verification**

Run: `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest backend/tests -q`
Expected: PASS

- [ ] **Step 2: Run frontend lint**

Run: `cd frontend && npm run lint`
Expected: PASS

- [ ] **Step 3: Run end-to-end manual smoke checks**

Verify in dev mode:
- `/assets/BTC` renders chart and provenance
- home chat answers Binance questions with real-source labels
- `/traces` displays endpoint/input/output summaries

- [ ] **Step 4: Run frontend build if environment allows**

Run: `cd frontend && npm run build`
Expected: PASS or document the existing Next.js worker crash if it remains environmental.

- [ ] **Step 5: Commit**

```bash
git add backend frontend
git commit -m "feat: complete phase 1 binance real chain"
```

---

Plan complete and saved to `docs/superpowers/plans/2026-03-17-binance-real-chain-implementation.md`. Ready to execute?
