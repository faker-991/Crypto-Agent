from __future__ import annotations

from typing import Any


ALLOWED_TIMEFRAMES = {"15m", "30m", "1h", "4h", "1d", "1w"}
ALLOWED_MARKET_TYPES = {"spot", "futures"}
ALLOWED_RESPONSE_STYLES = {"analysis", "investment_advice", "entry_setup"}
ALLOWED_ANALYSIS_INTENTS = {"trend", "entry", "risk_review", "mixed"}


def normalize_inputs(raw_inputs: dict[str, Any] | None) -> dict[str, Any]:
    normalized = dict(raw_inputs or {})

    asset = normalized.get("asset")
    if isinstance(asset, str) and asset.strip():
        normalized["asset"] = asset.strip().upper()
    else:
        normalized.pop("asset", None)

    normalized_timeframes = _normalize_timeframes(normalized.get("timeframes"))
    if normalized_timeframes:
        normalized["timeframes"] = normalized_timeframes
    else:
        normalized.pop("timeframes", None)

    market_type = _normalize_market_type(normalized.get("market_type"))
    if market_type:
        normalized["market_type"] = market_type
    else:
        normalized.pop("market_type", None)

    response_style = _normalize_enum(normalized.get("response_style"), ALLOWED_RESPONSE_STYLES)
    if response_style:
        normalized["response_style"] = response_style
    else:
        normalized.pop("response_style", None)

    analysis_intent = _normalize_enum(normalized.get("analysis_intent"), ALLOWED_ANALYSIS_INTENTS)
    if analysis_intent:
        normalized["analysis_intent"] = analysis_intent
    else:
        normalized.pop("analysis_intent", None)

    return normalized


def _normalize_timeframes(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    items: list[str] = []
    seen: set[str] = set()
    for item in value:
        if not isinstance(item, str):
            continue
        timeframe = item.strip().lower()
        if timeframe in ALLOWED_TIMEFRAMES and timeframe not in seen:
            seen.add(timeframe)
            items.append(timeframe)
    return items


def _normalize_market_type(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    lowered = value.strip().lower()
    aliases = {
        "现货": "spot",
        "spot": "spot",
        "合约": "futures",
        "永续": "futures",
        "期货": "futures",
        "futures": "futures",
    }
    resolved = aliases.get(lowered)
    return resolved if resolved in ALLOWED_MARKET_TYPES else None


def _normalize_enum(value: Any, allowed: set[str]) -> str | None:
    if not isinstance(value, str):
        return None
    lowered = value.strip().lower()
    return lowered if lowered in allowed else None
