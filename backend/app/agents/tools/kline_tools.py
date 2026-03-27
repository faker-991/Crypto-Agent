from math import sqrt
from statistics import mean

from app.schemas.kline import MarketDataPayload, TickerSummary
from app.services.market_data_service import MarketDataService


class KlineToolbox:
    def __init__(self, market_data_service: MarketDataService | None = None) -> None:
        self.market_data_service = market_data_service or MarketDataService()

    def get_klines(self, symbol: str, timeframe: str, market_type: str) -> MarketDataPayload:
        return self.market_data_service.get_klines(
            symbol=symbol,
            timeframe=timeframe,
            market_type=market_type,
        )

    def get_ticker(self, symbol: str, market_type: str) -> TickerSummary | None:
        canonical_market = self.market_data_service._resolve_market_key(market_type)
        return self.market_data_service._fetch_ticker_summary(symbol.upper(), canonical_market)

    def compute_indicators(self, candles: list) -> dict:
        closes = [float(candle.close) for candle in candles]
        highs = [float(candle.high) for candle in candles]
        lows = [float(candle.low) for candle in candles]

        values = {
            "sma_20": self._sma(closes, 20),
            "ema_20": self._ema(closes, 20),
            "rsi_14": self._rsi(closes, 14),
            "macd": None,
            "macd_signal": None,
            "bollinger_upper": None,
            "bollinger_middle": None,
            "bollinger_lower": None,
            "atr_14": self._atr(highs, lows, closes, 14),
        }

        macd_line, macd_signal = self._macd(closes)
        values["macd"] = macd_line
        values["macd_signal"] = macd_signal

        bollinger = self._bollinger(closes, 20, 2.0)
        if bollinger is not None:
            values["bollinger_upper"] = bollinger["upper"]
            values["bollinger_middle"] = bollinger["middle"]
            values["bollinger_lower"] = bollinger["lower"]

        missing = [name for name, value in values.items() if value is None]
        if missing:
            return {
                "status": "insufficient",
                "indicator_values": values,
                "missing_indicators": missing,
                "summary": "Not enough candle history to compute the full indicator set.",
            }
        return {
            "status": "success",
            "indicator_values": values,
            "missing_indicators": [],
            "summary": "Computed the full indicator set for this timeframe.",
        }

    def _sma(self, values: list[float], period: int) -> float | None:
        if len(values) < period:
            return None
        return round(mean(values[-period:]), 4)

    def _ema(self, values: list[float], period: int) -> float | None:
        if len(values) < period:
            return None
        multiplier = 2 / (period + 1)
        ema = mean(values[:period])
        for value in values[period:]:
            ema = ((value - ema) * multiplier) + ema
        return round(ema, 4)

    def _rsi(self, closes: list[float], period: int) -> float | None:
        if len(closes) <= period:
            return None
        deltas = [closes[index] - closes[index - 1] for index in range(1, len(closes))]
        window = deltas[-period:]
        gains = [delta for delta in window if delta > 0]
        losses = [abs(delta) for delta in window if delta < 0]
        average_gain = sum(gains) / period
        average_loss = sum(losses) / period
        if average_loss == 0:
            return 100.0
        rs = average_gain / average_loss
        return round(100 - (100 / (1 + rs)), 4)

    def _macd(self, closes: list[float]) -> tuple[float | None, float | None]:
        if len(closes) < 35:
            return None, None
        ema_12_series = self._ema_series(closes, 12)
        ema_26_series = self._ema_series(closes, 26)
        macd_series = [
            short - long
            for short, long in zip(ema_12_series[-len(ema_26_series):], ema_26_series)
        ]
        if len(macd_series) < 9:
            return None, None
        signal_series = self._ema_series(macd_series, 9)
        return round(macd_series[-1], 4), round(signal_series[-1], 4)

    def _ema_series(self, values: list[float], period: int) -> list[float]:
        if len(values) < period:
            return []
        multiplier = 2 / (period + 1)
        ema = mean(values[:period])
        series = [ema]
        for value in values[period:]:
            ema = ((value - ema) * multiplier) + ema
            series.append(ema)
        return series

    def _bollinger(self, closes: list[float], period: int, stdev_factor: float) -> dict | None:
        if len(closes) < period:
            return None
        window = closes[-period:]
        middle = mean(window)
        variance = sum((value - middle) ** 2 for value in window) / period
        deviation = sqrt(variance)
        return {
            "upper": round(middle + (stdev_factor * deviation), 4),
            "middle": round(middle, 4),
            "lower": round(middle - (stdev_factor * deviation), 4),
        }

    def _atr(self, highs: list[float], lows: list[float], closes: list[float], period: int) -> float | None:
        if len(closes) <= period:
            return None
        ranges: list[float] = []
        for index in range(1, len(closes)):
            true_range = max(
                highs[index] - lows[index],
                abs(highs[index] - closes[index - 1]),
                abs(lows[index] - closes[index - 1]),
            )
            ranges.append(true_range)
        if len(ranges) < period:
            return None
        return round(mean(ranges[-period:]), 4)
