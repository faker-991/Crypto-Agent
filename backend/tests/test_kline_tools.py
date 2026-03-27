from app.agents.tools.kline_tools import KlineToolbox
from app.schemas.kline import Candle


def _build_candles(count: int = 40) -> list[Candle]:
    candles: list[Candle] = []
    for index in range(count):
        open_price = 100.0 + index
        close_price = open_price + 1.5
        candles.append(
            Candle(
                symbol="BTC",
                timeframe="1d",
                open_time=index + 1,
                open=open_price,
                high=close_price + 2.0,
                low=open_price - 2.0,
                close=close_price,
                volume=1_000.0 + (index * 10),
            )
        )
    return candles


def test_compute_indicators_returns_core_indicator_values() -> None:
    toolbox = KlineToolbox()

    result = toolbox.compute_indicators(_build_candles())

    assert result["status"] == "success"
    assert result["missing_indicators"] == []
    values = result["indicator_values"]
    assert values["sma_20"] is not None
    assert values["ema_20"] is not None
    assert values["rsi_14"] is not None
    assert values["macd"] is not None
    assert values["macd_signal"] is not None
    assert values["bollinger_upper"] is not None
    assert values["bollinger_middle"] is not None
    assert values["bollinger_lower"] is not None
    assert values["atr_14"] is not None


def test_compute_indicators_returns_insufficient_for_short_history() -> None:
    toolbox = KlineToolbox()

    result = toolbox.compute_indicators(_build_candles(count=5))

    assert result["status"] == "insufficient"
    assert "rsi_14" in result["missing_indicators"]
    assert "bollinger_upper" in result["missing_indicators"]
