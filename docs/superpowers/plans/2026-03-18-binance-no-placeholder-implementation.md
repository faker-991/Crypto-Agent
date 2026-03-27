# Binance No-Placeholder Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove synthetic placeholder K-line data from the Binance market-data path and make backend, router, asset page, and traces expose explicit no-data/degraded states instead of fake candles.

**Architecture:** Keep the existing FastAPI + Next.js flow and current response shapes, but change degraded semantics. `MarketDataService` becomes real-data-only, `KlineAnalysisService` and router answer formatting become empty-candle-safe, and the frontend renders unavailable states rather than charts built from fabricated data.

**Tech Stack:** FastAPI, Pydantic, httpx, pytest, Next.js App Router, React, TypeScript, ESLint

---

## File Map

**Modify**

- `backend/app/clients/binance_market_adapter.py`
- `backend/app/services/market_data_service.py`
- `backend/app/services/kline_analysis_service.py`
- `backend/app/agents/kline_agent.py`
- `backend/app/services/router_service.py`
- `backend/app/api/research.py`
- `backend/app/schemas/kline.py`
- `backend/tests/test_market_data_service.py`
- `backend/tests/test_research_api.py`
- `backend/tests/test_kline_agent.py`
- `backend/tests/test_router_binance_execution.py`
- `frontend/app/assets/[symbol]/page.tsx`
- `frontend/components/kline-chart.tsx`
- `frontend/components/router-chat.tsx`
- `frontend/app/traces/page.tsx`
- `frontend/lib/asset-market-view.ts`
- `frontend/lib/trace-view.ts`
- `frontend/lib/api.ts`
- `frontend/tests/asset-market-view.test.mjs`
- `frontend/tests/trace-view.test.mjs`

---

## Chunk 1: Backend Real-Data Contract

### Task 1: Remove adapter-level placeholder usage from the business path

**Files:**
- Modify: `backend/app/clients/binance_market_adapter.py`
- Test: `backend/tests/test_market_data_service.py`

- [ ] **Step 1: Write the failing adapter-path assertion in the service test**

```python
def test_market_data_service_never_calls_placeholder_helper_on_fetch_failure() -> None:
    adapter = SpyFailingAdapter()
    service = MarketDataService(adapter=adapter)
    service.get_klines("BTCUSDT", "1d", "spot")
    assert adapter.placeholder_calls == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest backend/tests/test_market_data_service.py -q`
Expected: FAIL because fetch failure still triggers the placeholder helper.

- [ ] **Step 3: Write minimal implementation**

Implementation notes:
- Remove `get_placeholder_klines()` from the active market-data path.
- Keep the helper only if tests or non-user-visible utilities still reference it, but do not let production flow call it.

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest backend/tests/test_market_data_service.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/clients/binance_market_adapter.py backend/tests/test_market_data_service.py
git commit -m "refactor: remove adapter placeholder candles from business path"
```

### Task 2: Remove synthetic placeholder candles from market data service

**Files:**
- Modify: `backend/app/services/market_data_service.py`
- Modify: `backend/app/schemas/kline.py`
- Test: `backend/tests/test_market_data_service.py`

- [ ] **Step 1: Write the failing service test**

```python
def test_failed_klines_fetch_returns_empty_unavailable_payload() -> None:
    service = MarketDataService(adapter=FailingAdapter())
    payload = service.get_klines("BTCUSDT", "1d", "spot")
    assert payload.candles == []
    assert payload.source == "unavailable"
    assert payload.degraded_reason

def test_failed_futures_klines_fetch_returns_empty_unavailable_payload() -> None:
    service = MarketDataService(adapter=FailingAdapter())
    payload = service.get_klines("BTCUSDT", "4h", "futures")
    assert payload.candles == []
    assert payload.source == "unavailable"
    assert payload.market_type == "derivatives-trading-usds-futures"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest backend/tests/test_market_data_service.py -q`
Expected: FAIL because the service still returns placeholder candles and uses fallback semantics.

- [ ] **Step 3: Write minimal implementation**

Implementation notes:
- Change `MarketDataPayload.source` to allow `"unavailable"` instead of synthetic fallback semantics.
- On fetch failure, return:
  - `candles=[]`
  - `source="unavailable"`
  - `ticker_summary=None`
  - `degraded_reason=<message>`
- Preserve `endpoint_summary` when request metadata exists.
- For pre-validation failures, allow `endpoint_summary=None` per spec.

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest backend/tests/test_market_data_service.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/market_data_service.py backend/app/schemas/kline.py backend/tests/test_market_data_service.py
git commit -m "fix: remove synthetic market-data fallback candles"
```

### Task 3: Make research API preserve schema while exposing unavailable states

**Files:**
- Modify: `backend/app/api/research.py`
- Modify: `backend/tests/test_research_api.py`

- [ ] **Step 1: Write the failing research API test**

```python
def test_kline_research_returns_empty_candles_and_degraded_reason() -> None:
    response = read_kline_analysis(
        KlineResearchRequest(symbol="BTCUSDT", timeframes=["1d"], market_type="spot"),
        market_data_service=UnavailableMarketDataService(),
    )
    assert response.market_data["1d"].source == "unavailable"
    assert response.analyses["1d"].candles == []
    assert response.market_data["1d"].degraded_reason

def test_kline_research_returns_unavailable_futures_state() -> None:
    response = read_kline_analysis(
        KlineResearchRequest(symbol="BTCUSDT", timeframes=["4h"], market_type="futures"),
        market_data_service=UnavailableMarketDataService(),
    )
    assert response.market_data["4h"].source == "unavailable"
    assert response.market_data["4h"].market_type == "derivatives-trading-usds-futures"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest backend/tests/test_research_api.py -q`
Expected: FAIL because degraded semantics and empty-candle handling are not fully aligned.

- [ ] **Step 3: Write minimal implementation**

Implementation notes:
- Keep the existing response shape.
- Ensure `market_data[timeframe]` is the canonical degraded source.
- Ensure `analyses[timeframe].candles` mirrors the actual returned candles, including empty lists.

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest backend/tests/test_research_api.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/api/research.py backend/tests/test_research_api.py
git commit -m "fix: preserve unavailable market states in research api"
```

## Chunk 2: Analysis And Router Degraded Behavior

### Task 4: Make analysis services and kline agent empty-candle-safe

**Files:**
- Modify: `backend/app/services/kline_analysis_service.py`
- Modify: `backend/app/agents/kline_agent.py`
- Test: `backend/tests/test_kline_agent.py`

- [ ] **Step 1: Write the failing kline agent test**

```python
def test_kline_agent_returns_degraded_safe_analysis_when_candles_are_empty(tmp_path) -> None:
    agent = KlineAgent(tmp_path)
    agent.market_data_service = UnavailableMarketDataService()
    result = agent.execute("kline_scorecard", {"asset": "BTC", "timeframes": ["1d"], "market_type": "spot"})
    assert result["analyses"]["1d"]["candles"] == []
    assert "unavailable" in result["analyses"]["1d"]["conclusion"].lower()

def test_kline_agent_returns_degraded_safe_futures_analysis_when_candles_are_empty(tmp_path) -> None:
    agent = KlineAgent(tmp_path)
    agent.market_data_service = UnavailableMarketDataService()
    result = agent.execute("kline_scorecard", {"asset": "BTC", "timeframes": ["4h"], "market_type": "futures"})
    assert result["market_type"] == "derivatives-trading-usds-futures"
    assert result["analyses"]["4h"]["candles"] == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest backend/tests/test_kline_agent.py -q`
Expected: FAIL because analysis assumes candles exist and conclusion text is still optimized for real data.

- [ ] **Step 3: Write minimal implementation**

Implementation notes:
- `KlineAnalysisService` should return a stable empty-analysis summary when no candles are present.
- That summary must not imply a real technical trend.
- `KlineAgent` should keep provenance and degraded reason intact.

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest backend/tests/test_kline_agent.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/kline_analysis_service.py backend/app/agents/kline_agent.py backend/tests/test_kline_agent.py
git commit -m "fix: make kline analysis safe for unavailable market data"
```

### Task 5: Make router Binance answers transparently fail on unavailable data

**Files:**
- Modify: `backend/app/services/router_service.py`
- Test: `backend/tests/test_router_binance_execution.py`

- [ ] **Step 1: Write the failing router execution test**

```python
def test_router_returns_explicit_unavailable_answer_for_binance_query(tmp_path) -> None:
    service = RouterService(memory_root=tmp_path)
    service.kline_agent = StubUnavailableKlineAgent()
    result = service.route_and_execute("BTC 现货现在怎么样")
    assert "unavailable" in result["execution"]["answer"].lower()

def test_router_returns_explicit_unavailable_answer_for_futures_query(tmp_path) -> None:
    service = RouterService(memory_root=tmp_path)
    service.kline_agent = StubUnavailableKlineAgent()
    result = service.route_and_execute("BTC futures 4h 现在怎么样")
    assert "unavailable" in result["execution"]["answer"].lower()
    assert result["route"]["payload"]["market_type"] == "futures"

def test_router_uses_degraded_reason_as_only_unavailable_discriminator(tmp_path) -> None:
    service = RouterService(memory_root=tmp_path)
    service.kline_agent = StubNoCandlesButNotDegradedKlineAgent()
    result = service.route_and_execute("BTC 现货现在怎么样")
    assert "unavailable" not in result["execution"]["answer"].lower()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest backend/tests/test_router_binance_execution.py -q`
Expected: FAIL because router still formats market answers as if analysis succeeded.

- [ ] **Step 3: Write minimal implementation**

Implementation notes:
- Treat `degraded_reason != null` as the only degraded discriminator.
- If latest timeframe has `degraded_reason != null`, build an explicit failure answer.
- Preserve provenance and market summary without implying real analysis.

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest backend/tests/test_router_binance_execution.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/router_service.py backend/tests/test_router_binance_execution.py
git commit -m "fix: make router binance answers transparent on data failures"
```

## Chunk 3: Frontend No-Data States

### Task 6: Make asset page and chart render unavailable state instead of fake chart

**Files:**
- Modify: `frontend/app/assets/[symbol]/page.tsx`
- Modify: `frontend/components/kline-chart.tsx`
- Create: `frontend/lib/asset-market-view.ts`
- Create: `frontend/tests/asset-market-view.test.mjs`
- Modify: `frontend/lib/api.ts`

- [ ] **Step 1: Update the asset-page assumptions**

Implementation notes:
- When `candles.length === 0`, treat it as unavailable, not just empty.
- Show endpoint and degraded reason from `market_data`.
- Ensure ticker blocks handle `null` cleanly.
- Check both `spot` and `futures` views in the implementation.

- [ ] **Step 2: Write deterministic asset unavailable-state test**

```javascript
import test from "node:test";
import assert from "node:assert/strict";
import { buildAssetMarketView } from "../lib/asset-market-view.js";

test("buildAssetMarketView marks unavailable state from degraded_reason", () => {
  const view = buildAssetMarketView({ source: "unavailable", degraded_reason: "klines failed" });
  assert.equal(view.isUnavailable, true);
  assert.match(view.statusLabel, /unavailable/i);
});
```

- [ ] **Step 3: Run focused test to verify it fails**

Run: `cd frontend && node --test tests/asset-market-view.test.mjs`
Expected: FAIL because the pure view-model helper does not exist yet.

- [ ] **Step 4: Write minimal implementation**

Implementation notes:
- Extract asset-page unavailable-state derivation into a pure helper in `frontend/lib/asset-market-view.ts`.
- Drive page copy from that helper so behavior is deterministic and testable.
- `KlineChart` empty state copy should explicitly indicate missing live Binance data.
- Asset page should not imply “live feed” if `source="unavailable"`.
- Keep the current visual layout; only change semantics and error messaging.

- [ ] **Step 5: Run focused frontend checks**

Run:

```bash
cd frontend && node --test tests/asset-market-view.test.mjs
cd frontend && npm run lint
```

Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add frontend/app/assets/[symbol]/page.tsx frontend/components/kline-chart.tsx frontend/lib/asset-market-view.ts frontend/tests/asset-market-view.test.mjs frontend/lib/api.ts
git commit -m "fix: show unavailable states instead of fake kline charts"
```

### Task 7: Make homepage chat and traces render degraded states honestly

**Files:**
- Modify: `frontend/components/router-chat.tsx`
- Modify: `frontend/app/traces/page.tsx`
- Create: `frontend/lib/trace-view.ts`
- Create: `frontend/tests/trace-view.test.mjs`

- [ ] **Step 1: Update degraded-state UI requirements**

Implementation notes:
- Chat replies should clearly say real-time Binance data was unavailable.
- Trace cards should continue highlighting degraded nodes and show `source=unavailable`.
- Check both spot and futures wording paths in the UI copy.

- [ ] **Step 2: Write deterministic trace unavailable-state test**

```javascript
import test from "node:test";
import assert from "node:assert/strict";
import { summarizeTraceEvent } from "../lib/trace-view.js";

test("summarizeTraceEvent keeps degraded and endpoint details", () => {
  const event = summarizeTraceEvent({
    detail: { degraded: true, error: "klines failed", endpoint: "klines", source: "unavailable" },
  });
  assert.equal(event.degraded, true);
  assert.equal(event.endpoint, "klines");
});
```

- [ ] **Step 3: Run focused test to verify it fails**

Run: `cd frontend && node --test tests/trace-view.test.mjs`
Expected: FAIL because the pure trace helper does not exist yet.

- [ ] **Step 4: Write minimal implementation**

Implementation notes:
- Extract trace-card summarization into `frontend/lib/trace-view.ts`.
- Router chat and traces page should consume that helper so degraded semantics are deterministic.
- Avoid language that implies successful analysis when data is unavailable.

- [ ] **Step 5: Run focused frontend checks**

Run:

```bash
cd frontend && node --test tests/trace-view.test.mjs
cd frontend && npm run lint
```

Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add frontend/components/router-chat.tsx frontend/app/traces/page.tsx frontend/lib/trace-view.ts frontend/tests/trace-view.test.mjs
git commit -m "fix: surface unavailable binance states in chat and traces"
```

## Chunk 4: Verification

### Task 8: Run focused backend and frontend verification

**Files:**
- Test only

- [ ] **Step 1: Run focused backend regression suite**

Run:

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest \
  backend/tests/test_market_data_service.py \
  backend/tests/test_research_api.py \
  backend/tests/test_kline_agent.py \
  backend/tests/test_router_binance_execution.py \
  backend/tests/test_trace_api_real_chain.py -q
```

Expected: PASS

- [ ] **Step 2: Run frontend lint**

Run:

```bash
cd frontend && npm run lint
```

Expected: PASS

- [ ] **Step 3: Verify HTTP surfaces if dev servers are available**

Run:

```bash
curl -I -s http://127.0.0.1:3000/
curl -I -s http://127.0.0.1:3000/assets/BTC
curl -I -s http://127.0.0.1:3000/traces
curl -s http://127.0.0.1:8000/api/health
```

Expected:
- frontend routes return `200 OK`
- health returns `{"status":"ok"}`

- [ ] **Step 4: Re-run deterministic frontend unavailable-state tests**

Run:

```bash
cd frontend && node --test tests/asset-market-view.test.mjs tests/trace-view.test.mjs
```

Expected: PASS

- [ ] **Step 5: Commit verification-only metadata if needed**

```bash
# No commit unless implementation required follow-up fixes.
```
