# Asset Live Watchlist Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn `/assets/[symbol]` into a live monitoring console with a searchable persisted watchlist, real-time top-20 discovery, and 1-second refresh for the currently selected intraday chart.

**Architecture:** Add a dedicated backend asset-discovery and live-snapshot contract that keeps CoinGecko ranking/search and Binance symbol mapping on the server. Replace the current server-rendered asset detail page with a client-driven asset workspace that reuses watchlist persistence, polls one combined live endpoint, and removes the old thesis and secondary-timeframe sections.

**Tech Stack:** FastAPI, Pydantic, pytest, httpx, Next.js 15 App Router, React 19, TypeScript, ESLint

---

## Chunk 1: Backend Discovery And Live Snapshot Contract

### Task 1: Add schema coverage for discovery items and live payloads

**Files:**
- Create: `backend/app/schemas/assets.py`
- Test: `backend/tests/test_asset_api.py`

- [ ] **Step 1: Write failing schema/API tests for supported, unsupported, and degraded live payloads**

```python
from app.schemas.assets import AssetDiscoveryItem, AssetLiveSnapshot


def test_asset_live_snapshot_can_represent_unavailable_asset() -> None:
    payload = AssetLiveSnapshot(
        symbol="BTC",
        binance_symbol="BTCUSDT",
        name="Bitcoin",
        market_type="spot",
        timeframe="1m",
        is_supported=False,
        source="unavailable",
        candles=[],
        ticker_summary=None,
        endpoint_summary=None,
        degraded_reason="symbol is not supported on Binance spot",
        chart_summary=None,
    )

    assert payload.symbol == "BTC"
    assert payload.candles == []
    assert payload.source == "unavailable"
    assert payload.degraded_reason is not None


def test_asset_discovery_item_marks_support_state() -> None:
    item = AssetDiscoveryItem(
        symbol="BTC",
        name="Bitcoin",
        image="https://example.com/btc.png",
        market_cap=1,
        current_price=2,
        price_change_percentage_24h=3,
        binance_symbol="BTCUSDT",
        is_binance_supported=True,
    )

    assert item.symbol == "BTC"
    assert item.binance_symbol == "BTCUSDT"
    assert item.is_binance_supported is True
```

- [ ] **Step 2: Run the targeted backend tests to verify the new schema module is missing**

Run: `pytest backend/tests/test_asset_api.py -k "asset_live_snapshot or asset_discovery_item" -v`
Expected: FAIL with import or attribute errors for `app.schemas.assets`

- [ ] **Step 3: Create `backend/app/schemas/assets.py` with explicit discovery and live response models**

```python
from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.kline import Candle, EndpointSummary, TickerSummary


class AssetDiscoveryItem(BaseModel):
    symbol: str
    name: str | None = None
    image: str | None = None
    market_cap: float | int | None = None
    current_price: float | None = None
    price_change_percentage_24h: float | None = None
    binance_symbol: str | None = None
    is_binance_supported: bool


class AssetDiscoveryResponse(BaseModel):
    items: list[AssetDiscoveryItem] = Field(default_factory=list)


class AssetChartSummary(BaseModel):
    trend_regime: str
    breakout_signal: bool
    drawdown_state: str
    support_levels: list[float] = Field(default_factory=list)
    resistance_levels: list[float] = Field(default_factory=list)
    conclusion: str


class AssetLiveSnapshot(BaseModel):
    symbol: str
    binance_symbol: str | None = None
    name: str | None = None
    market_type: str
    timeframe: str
    is_supported: bool
    source: Literal["binance", "unavailable"]
    candles: list[Candle] = Field(default_factory=list)
    ticker_summary: TickerSummary | None = None
    endpoint_summary: EndpointSummary | None = None
    degraded_reason: str | None = None
    chart_summary: AssetChartSummary | None = None
```

- [ ] **Step 4: Re-run the schema tests**

Run: `pytest backend/tests/test_asset_api.py -k "asset_live_snapshot or asset_discovery_item" -v`
Expected: PASS

- [ ] **Step 5: Commit the schema slice if `.git` exists**

```bash
git add backend/app/schemas/assets.py backend/tests/test_asset_api.py
git commit -m "feat: add asset discovery and live snapshot schemas"
```

### Task 2: Build asset discovery and symbol-mapping service with tests first

**Files:**
- Create: `backend/app/services/asset_discovery_service.py`
- Modify: `backend/app/clients/external_research_adapter.py`
- Test: `backend/tests/test_asset_discovery_service.py`

- [ ] **Step 1: Write failing service tests for top-20 filtering, search mapping, and unsupported entries**

```python
from app.services.asset_discovery_service import AssetDiscoveryService


class StubResearchAdapter:
    def fetch_top_market_assets(self, limit: int) -> list[dict]:
        return [
            {"symbol": "btc", "name": "Bitcoin", "image": "btc.png", "market_cap": 10, "current_price": 1, "price_change_percentage_24h": 2},
            {"symbol": "abc", "name": "Unsupported", "image": "abc.png", "market_cap": 9, "current_price": 1, "price_change_percentage_24h": 2},
        ]

    def search_assets(self, query: str) -> list[dict]:
        return [
            {"symbol": "eth", "name": "Ethereum", "image": "eth.png", "market_cap_rank": 2},
            {"symbol": "bad", "name": "Bad Coin", "image": "bad.png", "market_cap_rank": 999},
        ]


class StubMarketDataService:
    def is_symbol_supported(self, binance_symbol: str, market_type: str = "spot") -> bool:
        return binance_symbol in {"BTCUSDT", "ETHUSDT"}


def test_top_assets_prefers_supported_symbols() -> None:
    service = AssetDiscoveryService(
        research_adapter=StubResearchAdapter(),
        market_data_service=StubMarketDataService(),
    )

    payload = service.get_top_assets(limit=20)

    assert payload.items[0].symbol == "BTC"
    assert all(item.is_binance_supported for item in payload.items)


def test_search_assets_returns_support_flags() -> None:
    service = AssetDiscoveryService(
        research_adapter=StubResearchAdapter(),
        market_data_service=StubMarketDataService(),
    )

    payload = service.search_assets("eth")

    assert payload.items[0].symbol == "ETH"
    assert payload.items[0].is_binance_supported is True
    assert payload.items[1].is_binance_supported is False
```

- [ ] **Step 2: Run the service tests to verify the service is missing**

Run: `pytest backend/tests/test_asset_discovery_service.py -v`
Expected: FAIL with import errors for `AssetDiscoveryService`

- [ ] **Step 3: Extend the external adapter with top-market and search methods**

```python
def fetch_top_market_assets(self, limit: int = 20) -> list[dict]:
    response = self.client.get(
        "https://api.coingecko.com/api/v3/coins/markets",
        params={
            "vs_currency": "usd",
            "order": "market_cap_desc",
            "per_page": limit,
            "page": 1,
            "price_change_percentage": "24h",
        },
    )
    response.raise_for_status()
    return response.json()


def search_assets(self, query: str) -> list[dict]:
    response = self.client.get(
        "https://api.coingecko.com/api/v3/search",
        params={"query": query},
    )
    response.raise_for_status()
    return response.json().get("coins", [])
```

- [ ] **Step 4: Implement `AssetDiscoveryService` to normalize base symbols, derive `{BASE}USDT`, and preserve unsupported search entries**

```python
class AssetDiscoveryService:
    def get_top_assets(self, limit: int = 20) -> AssetDiscoveryResponse:
        ...

    def search_assets(self, query: str) -> AssetDiscoveryResponse:
        ...

    def enrich_watchlist_symbols(self, symbols: list[str]) -> AssetDiscoveryResponse:
        ...

    def _map_item(self, item: dict, *, include_unsupported: bool) -> AssetDiscoveryItem | None:
        base_symbol = str(item.get("symbol", "")).upper()
        binance_symbol = f"{base_symbol}USDT" if base_symbol else None
        is_supported = bool(binance_symbol) and self.market_data_service.is_symbol_supported(binance_symbol, market_type="spot")
        ...
```

- [ ] **Step 5: Re-run the discovery service tests**

Run: `pytest backend/tests/test_asset_discovery_service.py -v`
Expected: PASS

- [ ] **Step 6: Commit the discovery service slice if `.git` exists**

```bash
git add backend/app/clients/external_research_adapter.py backend/app/services/asset_discovery_service.py backend/tests/test_asset_discovery_service.py
git commit -m "feat: add asset discovery service"
```

### Task 3: Add live asset endpoint behavior and router wiring with API tests first

**Files:**
- Create: `backend/app/api/assets.py`
- Modify: `backend/app/main.py`
- Modify: `backend/app/services/market_data_service.py`
- Test: `backend/tests/test_asset_api.py`

- [ ] **Step 1: Write failing API tests for top discovery, search, supported live payloads, and degraded unsupported routes**

```python
from fastapi.testclient import TestClient

from app.main import create_app


def test_get_top_assets_returns_items(tmp_path) -> None:
    app = create_app(memory_root=tmp_path, enable_scheduler=False)
    client = TestClient(app)

    response = client.get("/api/assets/discovery/top")

    assert response.status_code == 200
    assert "items" in response.json()


def test_get_live_asset_returns_unavailable_payload_for_unsupported_route(tmp_path) -> None:
    app = create_app(memory_root=tmp_path, enable_scheduler=False)
    client = TestClient(app)

    response = client.get("/api/assets/BAD/live?market=spot&timeframe=1m")

    assert response.status_code == 200
    payload = response.json()
    assert payload["symbol"] == "BAD"
    assert payload["is_supported"] is False
    assert payload["candles"] == []
    assert payload["source"] == "unavailable"
```

- [ ] **Step 2: Run the API tests to verify the router is missing**

Run: `pytest backend/tests/test_asset_api.py -v`
Expected: FAIL with 404s or missing dependency wiring

- [ ] **Step 3: Add `is_symbol_supported` and `get_live_snapshot` helpers to `MarketDataService`**

```python
def is_symbol_supported(self, binance_symbol: str, market_type: str = "spot") -> bool:
    payload = self.get_klines(symbol=binance_symbol, timeframe="1m", market_type=market_type)
    return payload.source == "binance"


def get_live_snapshot(self, symbol: str, timeframe: str, market_type: str) -> AssetLiveSnapshot:
    ...
```

- [ ] **Step 4: Implement `backend/app/api/assets.py` with `GET /api/assets/discovery/top`, `GET /api/assets/discovery/search`, and `GET /api/assets/{symbol}/live`**

```python
router = APIRouter(prefix="/api/assets", tags=["assets"])


@router.get("/discovery/top", response_model=AssetDiscoveryResponse)
def read_top_assets(...):
    return discovery_service.get_top_assets(limit=20)


@router.get("/discovery/search", response_model=AssetDiscoveryResponse)
def search_assets(q: str, ...):
    return discovery_service.search_assets(q)


@router.get("/{symbol}/live", response_model=AssetLiveSnapshot)
def read_live_asset(symbol: str, market: str = "spot", timeframe: str = "1m", ...):
    return live_service.get_live_snapshot(symbol=symbol, timeframe=timeframe, market_type=market)
```

- [ ] **Step 5: Wire the router and dependencies in `backend/app/main.py`**

```python
from app.api import assets, conversations, memory, paper_trading, planner, research, trace, watchlist
...
asset_discovery_service = AssetDiscoveryService(market_data_service=market_data_service)
...
app.dependency_overrides[assets.get_asset_discovery_service] = lambda: asset_discovery_service
app.dependency_overrides[assets.get_market_data_service] = lambda: market_data_service
...
app.include_router(assets.router)
```

- [ ] **Step 6: Run the new backend tests plus existing watchlist and market data tests**

Run: `pytest backend/tests/test_asset_api.py backend/tests/test_asset_discovery_service.py backend/tests/test_watchlist_api.py backend/tests/test_market_data_service.py -v`
Expected: PASS

- [ ] **Step 7: Commit the backend API slice if `.git` exists**

```bash
git add backend/app/api/assets.py backend/app/main.py backend/app/services/market_data_service.py backend/tests/test_asset_api.py
git commit -m "feat: add asset discovery and live asset api"
```

## Chunk 2: Frontend Asset Workspace And Polling

### Task 4: Extend frontend API types and client helpers first

**Files:**
- Modify: `frontend/lib/api.ts`
- Test: `frontend/app/assets/[symbol]/page.tsx`

- [ ] **Step 1: Add typed client contracts for discovery and live snapshot payloads**

```ts
export type AssetDiscoveryItem = {
  symbol: string;
  name: string | null;
  image: string | null;
  market_cap: number | null;
  current_price: number | null;
  price_change_percentage_24h: number | null;
  binance_symbol: string | null;
  is_binance_supported: boolean;
};

export type AssetLiveSnapshot = {
  symbol: string;
  binance_symbol: string | null;
  name: string | null;
  market_type: string;
  timeframe: string;
  is_supported: boolean;
  source: "binance" | "unavailable";
  candles: Candle[];
  ticker_summary: TickerSummary | null;
  endpoint_summary: EndpointSummary | null;
  degraded_reason: string | null;
  chart_summary: {
    trend_regime: string;
    breakout_signal: boolean;
    drawdown_state: string;
    support_levels: number[];
    resistance_levels: number[];
    conclusion: string;
  } | null;
};
```

- [ ] **Step 2: Add helper functions for top discovery, search, and live polling**

```ts
export function fetchTopAssets(): Promise<{ items: AssetDiscoveryItem[] }> {
  return getJson("/api/assets/discovery/top", { items: [] });
}

export function searchAssets(query: string): Promise<{ items: AssetDiscoveryItem[] }> {
  return getJson(`/api/assets/discovery/search?q=${encodeURIComponent(query)}`, { items: [] });
}

export function fetchLiveAsset(symbol: string, marketType: MarketType, timeframe: string): Promise<AssetLiveSnapshot> {
  return getJson(
    `/api/assets/${encodeURIComponent(symbol)}/live?market=${marketType}&timeframe=${encodeURIComponent(timeframe)}`,
    {
      symbol,
      binance_symbol: null,
      name: null,
      market_type: marketType,
      timeframe,
      is_supported: false,
      source: "unavailable",
      candles: [],
      ticker_summary: null,
      endpoint_summary: null,
      degraded_reason: "live asset request failed",
      chart_summary: null,
    },
  );
}
```

- [ ] **Step 3: Run lint to catch type drift before building UI**

Run: `cd frontend && npm run lint`
Expected: PASS

### Task 5: Replace the current asset page with a client-driven live console

**Files:**
- Create: `frontend/components/asset-live-workspace.tsx`
- Create: `frontend/components/asset-selector.tsx`
- Create: `frontend/components/asset-live-right-rail.tsx`
- Modify: `frontend/app/assets/[symbol]/page.tsx`
- Modify: `frontend/components/kline-chart.tsx`

- [ ] **Step 1: Replace the page-level thesis + secondary-view fetches with a thin route shell**

```tsx
export default async function AssetPage({ params, searchParams }: AssetPageProps) {
  const { symbol } = await params;
  const search = (await searchParams) ?? {};
  const marketType = normalizeMarketType(readSingleParam(search.market));
  const timeframe = readSingleParam(search.timeframe) ?? "1m";

  return <AssetLiveWorkspace initialSymbol={symbol} initialMarketType={marketType} initialTimeframe={timeframe} />;
}
```

- [ ] **Step 2: Implement `AssetLiveWorkspace` to load watchlist, top assets, and the current live snapshot**

```tsx
const SUPPORTED_TIMEFRAMES = ["1m", "5m", "15m", "1h"] as const;

useEffect(() => {
  startTransition(async () => {
    const [watchlist, topAssets, live] = await Promise.all([
      fetchWatchlist(),
      fetchTopAssets(),
      fetchLiveAsset(symbol, marketType, timeframe),
    ]);
    ...
  });
}, [symbol, marketType, timeframe]);
```

- [ ] **Step 3: Add a 1-second polling loop that refreshes only the selected asset**

```tsx
useEffect(() => {
  const timer = window.setInterval(() => {
    void fetchLiveAsset(symbol, marketType, timeframe).then(setLiveSnapshot);
  }, 1000);
  return () => window.clearInterval(timer);
}, [symbol, marketType, timeframe]);
```

- [ ] **Step 4: Implement `AssetSelector` with persisted watchlist chips, top-20 suggestions, search, add, and route navigation**

```tsx
type AssetSelectorProps = {
  currentSymbol: string;
  watchlist: WatchlistItem[];
  topAssets: AssetDiscoveryItem[];
  onAddToWatchlist: (symbol: string) => Promise<void>;
  onNavigateToAsset: (symbol: string) => void;
};
```

- [ ] **Step 5: Update the main console copy and layout to remove `Research note` and `Other timeframes`**

```tsx
<section className="space-y-6">
  <AssetSelector ... />
  <div className="overflow-hidden rounded-[2.25rem] ...">
    <KlineChart
      candles={liveSnapshot.candles}
      supportLevels={liveSnapshot.chart_summary?.support_levels ?? []}
      resistanceLevels={liveSnapshot.chart_summary?.resistance_levels ?? []}
      timeframeLabel={`${timeframe} view`}
      statusLabel={liveSnapshot.source === "binance" ? "live" : "unavailable"}
      emptyLabel="Live Binance data is unavailable for this timeframe. No synthetic candles are shown."
    />
  </div>
</section>
```

- [ ] **Step 6: Move the live market metrics into a dedicated right rail component tied to the combined live payload**

```tsx
<AssetLiveRightRail
  marketLabel={marketLabel}
  ticker={liveSnapshot.ticker_summary}
  endpoint={liveSnapshot.endpoint_summary}
  degradedReason={liveSnapshot.degraded_reason}
  source={liveSnapshot.source}
/>
```

- [ ] **Step 7: Ensure unsupported selected assets stay renderable but disabled for chart interactions**

```tsx
const isUnavailable = !liveSnapshot.is_supported || liveSnapshot.source === "unavailable";
const statusText = liveSnapshot.degraded_reason ?? "实时 Binance 数据可用";
```

- [ ] **Step 8: Run lint and production build after the UI rewrite**

Run: `cd frontend && npm run lint && npm run build`
Expected: PASS

- [ ] **Step 9: Commit the frontend asset workspace slice if `.git` exists**

```bash
git add frontend/app/assets/[symbol]/page.tsx frontend/components/asset-live-workspace.tsx frontend/components/asset-selector.tsx frontend/components/asset-live-right-rail.tsx frontend/components/kline-chart.tsx frontend/lib/api.ts
git commit -m "feat: redesign asset page as live watchlist workspace"
```

## Chunk 3: Watchlist Integration And Verification

### Task 6: Connect selector actions to persisted watchlist and verify degraded paths

**Files:**
- Modify: `frontend/components/asset-live-workspace.tsx`
- Modify: `frontend/components/asset-selector.tsx`
- Test: `backend/tests/test_watchlist_api.py`

- [ ] **Step 1: Add optimistic add/remove handlers that reuse existing watchlist endpoints**

```tsx
async function handleAddToWatchlist(symbol: string) {
  const next = await addWatchlistItem({ symbol, status: "watch", priority: 2 });
  setWatchlist(next.assets);
}

async function handleRemoveFromWatchlist(symbol: string) {
  const next = await removeWatchlistItem(symbol);
  setWatchlist(next.assets);
}
```

- [ ] **Step 2: Keep unsupported watchlist assets visible but label them as unavailable**

```tsx
const unsupportedSymbols = new Set(topAssets.filter((item) => !item.is_binance_supported).map((item) => item.symbol));
```

- [ ] **Step 3: Re-run backend watchlist tests to verify no persistence regression**

Run: `pytest backend/tests/test_watchlist_api.py -v`
Expected: PASS

### Task 7: Do full-stack verification and document manual checks

**Files:**
- Modify: `docs/superpowers/plans/2026-03-24-asset-live-watchlist-implementation.md`

- [ ] **Step 1: Run the targeted backend suite**

Run: `pytest backend/tests/test_asset_api.py backend/tests/test_asset_discovery_service.py backend/tests/test_watchlist_api.py backend/tests/test_market_data_service.py -v`
Expected: PASS

- [ ] **Step 2: Run the frontend static checks**

Run: `cd frontend && npm run lint && npm run build`
Expected: PASS

- [ ] **Step 3: Manually verify the asset workflow in the browser**

Run:

```bash
cd frontend
npm run dev
```

Manual checks:
- `/assets/BTC` shows selector + live console, not `Research note` or `Other timeframes`
- selector loads persisted watchlist and top-market suggestions
- search can add a Binance-supported asset
- selecting a new asset updates the route
- `1m / 5m / 15m / 1h` controls are present
- only the active asset visibly refreshes every second
- unsupported assets show an honest unavailable state without crashing the page

- [ ] **Step 4: If `.git` exists, make the final integration commit**

```bash
git add backend frontend docs/superpowers/plans/2026-03-24-asset-live-watchlist-implementation.md
git commit -m "feat: add live asset watchlist workspace"
```
