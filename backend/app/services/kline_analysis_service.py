from app.schemas.kline import Candle, MarketDataPayload, TimeframeAnalysis


class KlineAnalysisService:
    def analyze_timeframe(self, candles: list[Candle] | MarketDataPayload) -> TimeframeAnalysis:
        candle_list = list(candles)
        if not candle_list:
            return TimeframeAnalysis(
                trend_regime="unavailable",
                support_levels=[],
                resistance_levels=[],
                breakout_signal=False,
                drawdown_state="unavailable",
                conclusion="Real-time Binance data unavailable for this timeframe.",
                candles=[],
            )

        first_close = candle_list[0].close
        last_close = candle_list[-1].close
        highest_high = max(candle.high for candle in candle_list)
        lowest_low = min(candle.low for candle in candle_list)
        average_volume = sum(candle.volume for candle in candle_list[:-1]) / max(
            len(candle_list) - 1,
            1,
        )
        breakout_signal = False
        if len(candle_list) > 1:
            previous_high = max(candle.high for candle in candle_list[:-1])
            breakout_signal = (
                candle_list[-1].volume > average_volume * 1.2
                and candle_list[-1].close >= previous_high
            )

        if last_close > first_close * 1.05:
            trend_regime = "uptrend"
        elif last_close < first_close * 0.95:
            trend_regime = "downtrend"
        else:
            trend_regime = "range"

        drawdown_ratio = (highest_high - last_close) / highest_high
        if drawdown_ratio < 0.08:
            drawdown_state = "near-high"
        elif drawdown_ratio < 0.2:
            drawdown_state = "reaccumulation"
        else:
            drawdown_state = "deep-drawdown"

        conclusion = (
            f"{trend_regime} on this timeframe with support near {lowest_low:.2f} "
            f"and resistance near {highest_high:.2f}."
        )

        return TimeframeAnalysis(
            trend_regime=trend_regime,
            support_levels=[round(lowest_low, 2)],
            resistance_levels=[round(highest_high, 2)],
            breakout_signal=breakout_signal,
            drawdown_state=drawdown_state,
            conclusion=conclusion,
            candles=candle_list,
        )
