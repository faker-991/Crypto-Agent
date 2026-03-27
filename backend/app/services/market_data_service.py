import httpx

from app.clients.binance_market_adapter import BinanceMarketAdapter
from app.schemas.assets import AssetChartSummary, AssetLiveSnapshot
from app.schemas.kline import (
    Candle,
    EndpointSummary,
    MarketDataPayload,
    TickerSummary,
)
from app.services.kline_analysis_service import KlineAnalysisService


class MarketDataService:
    def __init__(self, adapter: BinanceMarketAdapter | None = None) -> None:
        self.adapter = adapter or BinanceMarketAdapter()
        self.analysis_service = KlineAnalysisService()

    def get_klines(self, symbol: str, timeframe: str, market_type: str) -> MarketDataPayload:
        normalized_symbol = symbol.upper()
        canonical_market = self._resolve_market_key(market_type)
        ticker_summary = self._fetch_ticker_summary(normalized_symbol, canonical_market)
        request = self.adapter.build_kline_request(
            symbol=normalized_symbol,
            timeframe=timeframe,
            market_type=canonical_market,
            limit=120,
        )

        endpoint_summary: EndpointSummary | None = None
        degraded_reason: str | None = None
        raw_klines: list[tuple[int, float, float, float, float, float]] = []
        try:
            raw_klines = self._fetch_raw_klines(normalized_symbol, timeframe, canonical_market)
            endpoint_summary = EndpointSummary(**request.metadata)
            source = "binance"
        except (httpx.HTTPError, RuntimeError) as exc:
            endpoint_summary = EndpointSummary(**request.metadata)
            source = "unavailable"
            degraded_reason = f"klines fetch failed: {exc}"
        except Exception:  # pragma: no cover - leave other errors to bubble up
            raise

        candles = self._normalize_candles(normalized_symbol, timeframe, raw_klines)

        return MarketDataPayload(
            symbol=normalized_symbol,
            timeframe=timeframe,
            market_type=canonical_market,
            source=source,
            candles=candles,
            endpoint_summary=endpoint_summary,
            ticker_summary=ticker_summary,
            degraded_reason=degraded_reason,
        )

    def _resolve_market_key(self, market_type: str) -> str:
        registry = getattr(self.adapter, "registry", None)
        if registry is None:
            return "derivatives-trading-usds-futures" if market_type == "futures" else market_type
        return registry.resolve_market_key(market_type)

    def _fetch_raw_klines(
        self,
        symbol: str,
        timeframe: str,
        canonical_market: str,
    ) -> list[tuple[int, float, float, float, float, float]]:
        if canonical_market == "spot":
            return self.adapter.fetch_spot_klines(symbol=symbol, timeframe=timeframe, limit=120)
        if canonical_market == "derivatives-trading-usds-futures":
            return self.adapter.fetch_futures_klines(symbol=symbol, timeframe=timeframe, limit=120)
        raise ValueError(f"Unsupported market type: {canonical_market}")

    def _fetch_ticker_summary(self, symbol: str, canonical_market: str) -> TickerSummary | None:
        try:
            if canonical_market == "spot":
                payload = self.adapter.fetch_spot_ticker(symbol)
            elif canonical_market == "derivatives-trading-usds-futures":
                payload = self.adapter.fetch_futures_ticker(symbol)
            else:
                return None
            return TickerSummary(**payload["ticker"])
        except Exception:
            return None

    def is_symbol_supported(self, binance_symbol: str, market_type: str = "spot") -> bool:
        canonical_market = self._resolve_market_key(market_type)
        try:
            if canonical_market == "spot":
                self.adapter.fetch_spot_ticker(binance_symbol)
            elif canonical_market == "derivatives-trading-usds-futures":
                self.adapter.fetch_futures_ticker(binance_symbol)
            else:
                return False
        except Exception:
            return False
        return True

    def get_spot_ticker_summary(self, symbol: str) -> TickerSummary | None:
        normalized_symbol = self.adapter._normalize_symbol(symbol)
        return self._fetch_ticker_summary(normalized_symbol, "spot")

    def list_spot_searchable_assets(self) -> list[dict[str, str]]:
        payload = self.adapter.fetch_spot_exchange_info()
        symbols = payload.get("symbols", []) if isinstance(payload, dict) else []
        assets: list[dict[str, str]] = []
        seen_base_assets: set[str] = set()

        for item in symbols:
            if not isinstance(item, dict):
                continue

            symbol = str(item.get("symbol", "")).upper().strip()
            base_asset = str(item.get("baseAsset", "")).upper().strip()
            quote_asset = str(item.get("quoteAsset", "")).upper().strip()
            status = str(item.get("status", "")).upper().strip()
            is_spot_allowed = item.get("isSpotTradingAllowed")

            if not symbol or not base_asset or quote_asset != "USDT" or status != "TRADING":
                continue
            if is_spot_allowed is False or base_asset in seen_base_assets:
                continue

            seen_base_assets.add(base_asset)
            assets.append({"symbol": symbol, "base_asset": base_asset})

        return assets

    def get_live_snapshot(self, symbol: str, timeframe: str, market_type: str) -> AssetLiveSnapshot:
        base_symbol = symbol.upper().strip()
        binance_symbol = self.adapter._normalize_symbol(base_symbol)
        canonical_market = self._resolve_market_key(market_type)
        name = None

        if not self.is_symbol_supported(binance_symbol, market_type=market_type):
            return AssetLiveSnapshot(
                symbol=base_symbol,
                binance_symbol=binance_symbol,
                name=name,
                market_type=canonical_market,
                timeframe=timeframe,
                is_supported=False,
                source="unavailable",
                candles=[],
                ticker_summary=None,
                endpoint_summary=None,
                degraded_reason=f"symbol is not supported on Binance {market_type}",
                chart_summary=None,
            )

        payload = self.get_klines(symbol=binance_symbol, timeframe=timeframe, market_type=market_type)
        analysis = self.analysis_service.analyze_timeframe(payload)

        return AssetLiveSnapshot(
            symbol=base_symbol,
            binance_symbol=binance_symbol,
            name=name,
            market_type=payload.market_type,
            timeframe=timeframe,
            is_supported=payload.source == "binance",
            source=payload.source,
            candles=payload.candles,
            ticker_summary=payload.ticker_summary,
            endpoint_summary=payload.endpoint_summary,
            degraded_reason=payload.degraded_reason,
            chart_summary=AssetChartSummary(
                trend_regime=analysis.trend_regime,
                breakout_signal=analysis.breakout_signal,
                drawdown_state=analysis.drawdown_state,
                support_levels=analysis.support_levels,
                resistance_levels=analysis.resistance_levels,
                conclusion=analysis.conclusion,
            ),
        )

    def _normalize_candles(
        self,
        symbol: str,
        timeframe: str,
        raw_klines: list[tuple[int, float, float, float, float, float]],
    ) -> list[Candle]:
        return [
            Candle(
                symbol=symbol,
                timeframe=timeframe,
                open_time=item[0],
                open=item[1],
                high=item[2],
                low=item[3],
                close=item[4],
                volume=item[5],
            )
            for item in raw_klines
        ]
