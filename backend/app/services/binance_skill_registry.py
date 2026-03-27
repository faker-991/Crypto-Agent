from pathlib import Path


SKILL_SPECS = {
    "spot": {
        "base_url": "https://api.binance.com",
        "public_endpoints": {
            "klines": "/api/v3/klines",
            "ticker": "/api/v3/ticker/24hr",
            "test-order": "/api/v3/order/test",
        },
    },
    "derivatives-trading-usds-futures": {
        "base_url": "https://fapi.binance.com",
        "public_endpoints": {
            "klines": "/fapi/v1/klines",
            "funding-rate": "/fapi/v1/fundingRate",
            "open-interest": "/fapi/v1/openInterest",
            "test-order": "/fapi/v1/order/test",
        },
    },
    "alpha": {
        "base_url": "https://www.binance.com",
        "public_endpoints": {
            "klines": "/bapi/defi/v1/public/alpha-trade/klines",
            "ticker": "/bapi/defi/v1/public/alpha-trade/ticker",
        },
    },
}

MARKET_TYPE_ALIASES = {
    "spot": "spot",
    "futures": "derivatives-trading-usds-futures",
    "derivatives-trading-usds-futures": "derivatives-trading-usds-futures",
    "alpha": "alpha",
}


class BinanceSkillRegistry:
    def __init__(self, skill_roots: list[Path] | None = None) -> None:
        home = Path.home()
        self.skill_roots = skill_roots or [home / ".codex" / "skills", home / ".agents" / "skills"]

    def get_installed_skills(self) -> list[str]:
        installed = []
        for name in SKILL_SPECS:
            if self._find_skill_dir(name) is not None:
                installed.append(name)
        return installed

    def resolve_market_key(self, market_type: str) -> str:
        try:
            return MARKET_TYPE_ALIASES[market_type]
        except KeyError as exc:
            raise ValueError(f"Unsupported market type: {market_type}") from exc

    def get_spec(self, market_type: str) -> dict:
        key = self.resolve_market_key(market_type)
        return SKILL_SPECS[key]

    def get_capabilities(self) -> dict[str, list[str]]:
        capabilities = {}
        for name in self.get_installed_skills():
            capabilities[name] = sorted(SKILL_SPECS[name]["public_endpoints"].keys())
        return capabilities

    def _find_skill_dir(self, name: str) -> Path | None:
        for root in self.skill_roots:
            path = root / name / "SKILL.md"
            if path.exists():
                return path.parent
        return None
