# Asset Live Watchlist And Intraday Chart Design

Date: 2026-03-24

## Context

The current asset page is still organized like a research detail page:

- it fetches fixed timeframes `1d`, `4h`, and `1w`
- it shows `Research note`
- it shows `Other timeframes`
- it does not provide a usable asset selector or an intraday monitoring workflow

The user wants to turn this page into a live monitoring console:

- a selectable watchlist on the asset page
- default choices coming from the real-time top 20 coins by market cap
- the ability to search and add other coins
- only assets supported by Binance should be chartable
- current asset price and chart should refresh every second
- chart timeframes should be `1m`, `5m`, `15m`, and `1h`
- the `Research note` and `Other timeframes` sections should be removed

The watchlist should be persisted through the existing backend watchlist system rather than becoming page-local state.

## User-Approved Direction

The user approved these specific decisions:

- asset selector form: top searchable selector rather than a fixed side list
- top assets source: real-time top 20 by market cap
- search source: CoinGecko search, then map to Binance-supported chart assets
- real-time refresh scope: only the currently selected asset updates every second
- watchlist persistence: reuse the existing backend watchlist
- remove the two current modules:
  - `Research note`
  - `Other timeframes`

## Goals

- Turn `/assets/[symbol]` into a live single-asset monitoring page.
- Add a top-level asset selector with:
  - current watchlist
  - top 20 market-cap suggestions
  - search-and-add behavior
- Provide intraday chart views:
  - `1m`
  - `5m`
  - `15m`
  - `1h`
- Refresh the active asset price and current chart every second.
- Reuse existing watchlist persistence instead of inventing a second list store.

## Non-Goals

- No websocket market streaming in this iteration.
- No redesign of the memory page or dashboard page.
- No full localization work beyond what this page needs to display.
- No synthetic market data when Binance data is unavailable.

## Chosen Architecture

This should be implemented as a backend-assisted single-page enhancement:

- keep asset discovery and mapping in the backend
- keep live asset snapshots in the backend
- convert the asset page from server-only rendering into a client-driven page shell for the interactive portions
- reuse existing watchlist add/remove endpoints for persistence

This avoids pushing CoinGecko and Binance stitching into the frontend and keeps mapping and fallback logic centralized.

## Data Sources

### Top 20 By Market Cap

Use CoinGecko markets data as the ranking source:

- `coins/markets`
- ordered by market cap descending
- limited to 20

Each result should be mapped to a Binance chart symbol.

### Search

Use CoinGecko search or market lookup as the discovery source, then map results into Binance-supported assets.

Only results that can be mapped to a Binance-supported chart asset should be addable from the UI.

### Live Price And Chart

Use existing Binance-backed market data services for:

- ticker summary
- kline/candlestick data

Refresh only the currently selected asset and currently selected timeframe every second.

## Binance Mapping Rules

Asset discovery results must be mapped to Binance chart symbols using a strict backend rule:

- first try `{BASE}USDT`
- treat that as supported only if Binance market-data retrieval succeeds for the requested market
- if mapping fails, mark the discovery result as unsupported

Unsupported assets may be shown in search results but must not be addable to the active chart watchlist.

## Canonical Asset Identity

This flow must distinguish between the asset identity shown to users and the transport symbol used for Binance calls:

- canonical route, UI, and watchlist identity is the base asset symbol, such as `BTC`
- Binance transport identity is a derived symbol such as `BTCUSDT`
- `/assets/[symbol]` should continue using the base symbol form
- `/api/assets/{symbol}/live` should accept the base symbol form
- watchlist persistence should store the base symbol, not the Binance transport symbol

Backend discovery and live responses may include both forms, but the base symbol is the canonical key that ties together routing, watchlist persistence, and selector state.

## Market-Type Rules

Support and persistence rules should stay stable even when the page allows a market toggle:

- discovery support should be determined with the default spot mapping rule using `{BASE}USDT`
- watchlist entries should remain market-agnostic and store only the base symbol
- the page may still request `spot` or `futures` on the live endpoint for a selected watchlist asset
- if a symbol is valid for spot but unavailable for futures, the asset should remain selectable and watchlisted
- futures unavailability should be represented as a degraded live state rather than removing the asset from the page

## Page Design

### Top Asset Selector

Add a new selector area at the top of the asset page that includes:

- current persisted watchlist items
- top 20 market-cap suggestions
- search input
- search results
- add-to-watchlist action

Selecting any supported asset should navigate to its asset page route and refresh the live console for that asset.

### Main Console

Keep the visual weight on the main chart console, but make it intraday-first:

- selected asset symbol and name
- current live price
- 24h change
- market type toggle
- timeframe toggle:
  - `1m`
  - `5m`
  - `15m`
  - `1h`
- candlestick chart
- current technical summary tiles such as trend, breakout, and drawdown

### Right Rail

Keep the right-side market detail summary, but make it explicitly live and tied to the selected asset:

- last price
- 24h change
- open
- volume
- bid
- ask
- source
- endpoint
- data status

### Removed Sections

Remove these sections entirely:

- `Research note`
- `Other timeframes`

## Backend API Design

### Asset Discovery Endpoints

Add endpoints under a dedicated asset discovery route:

- `GET /api/assets/discovery/top`
- `GET /api/assets/discovery/search?q=...`

Suggested item shape:

```json
{
  "symbol": "BTC",
  "name": "Bitcoin",
  "image": "https://...",
  "market_cap": 1000000,
  "current_price": 90000,
  "price_change_percentage_24h": 1.23,
  "binance_symbol": "BTCUSDT",
  "is_binance_supported": true
}
```

Response rules:

- `top` returns up to 20 items sorted by market cap descending and should prefer assets that are Binance-supported under the default spot mapping rule
- `search` returns mapped search matches
- unsupported results may be returned, but must be marked clearly
- persisted watchlist entries that are no longer Binance-supported should still be returned to the frontend, but must be marked unsupported

### Live Asset Snapshot Endpoint

Add a combined live endpoint:

- `GET /api/assets/{symbol}/live?market=spot&timeframe=1m`

This endpoint should return one backend-stitched response containing:

- `symbol`
- `binance_symbol`
- `market_type`
- `timeframe`
- `is_supported`
- `candles`
- `source`
- `ticker_summary`
- `endpoint_summary`
- `degraded_reason` when present
- `chart_summary` when present
- `name` when available

This endpoint should be used by the frontend polling loop so the UI only performs one request per second for the active asset.

Contract rules:

- `candles` must always be an array, including degraded or unsupported responses
- supported responses should reuse the existing ticker and endpoint summary shapes where possible
- degraded or unavailable responses should return:
  - `is_supported: false` or an explicit degraded supported state as appropriate
  - `candles: []`
  - `source: "unavailable"`
  - a non-null `degraded_reason`
- unsupported current-route symbols should not hard-fail the page contract; they should return an unavailable live payload that the frontend can render honestly

## Frontend Architecture

### Page Shell

The asset route should keep route-based selection via `/assets/[symbol]`, but the interactive content should move into client components so the selector and live polling can update smoothly.

### Suggested Components

- asset page shell
- asset selector
- asset live console
- asset live right rail

These do not need to be over-decomposed, but the chart polling and selector logic should not live in one giant page file.

## Watchlist Integration

Reuse the existing watchlist backend:

- read watchlist contents for the selector’s persisted list
- add supported assets through the existing add endpoint
- optionally remove from the selector through the existing remove endpoint

The asset page should not invent a separate persisted asset list.

## Polling Strategy

The live page should poll only the active asset:

- interval: once per second
- fetch target: the combined live endpoint
- restart polling when symbol, market type, or timeframe changes
- stop polling on unmount

Top 20 suggestions and search results do not need per-second refresh.

## Error Handling

- If top 20 discovery fails:
  - keep the selector usable with persisted watchlist and manual search
- If search fails:
  - show a local error state in the selector without breaking the page
- If Binance live data fails for the selected asset/timeframe:
  - keep the page visible
  - show unavailable state in chart and right rail
  - do not fabricate candles
- If a discovered asset is unsupported on Binance:
  - show it as unsupported
  - disable add/select actions for chart use
- If the current routed asset exists in the watchlist but is no longer supported:
  - keep the route renderable
  - show the asset as unsupported
  - return an unavailable live payload rather than a brittle page-level failure

## Testing

Backend tests should verify:

- top discovery returns mapped top-20 items
- search discovery maps CoinGecko search results into Binance-supported items
- unsupported assets are marked correctly
- live asset endpoint returns ticker, candles, and metadata for supported assets
- live endpoint degrades honestly when Binance data is unavailable

Frontend tests or manual verification should verify:

- asset selector shows persisted watchlist plus top-20 suggestions
- manual search can add a supported asset to watchlist
- selecting a supported asset updates the route
- only the active asset updates every second
- timeframe buttons show `1m`, `5m`, `15m`, `1h`
- `Research note` and `Other timeframes` are gone

## Rollout

1. Add backend discovery and live asset APIs.
2. Extend frontend API client types.
3. Refactor asset page into a live selector + live console layout.
4. Reuse watchlist persistence for add/remove behavior.
5. Verify live refresh behavior and degraded states manually.
