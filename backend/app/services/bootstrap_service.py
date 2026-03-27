import json
from pathlib import Path


class BootstrapService:
    def __init__(self, memory_root: Path) -> None:
        self.memory_root = memory_root

    def ensure_files(self) -> None:
        self.memory_root.mkdir(parents=True, exist_ok=True)
        (self.memory_root / "theses").mkdir(parents=True, exist_ok=True)
        (self.memory_root / "assets").mkdir(parents=True, exist_ok=True)
        (self.memory_root / "journal").mkdir(parents=True, exist_ok=True)
        (self.memory_root / "reports" / "weekly").mkdir(parents=True, exist_ok=True)
        (self.memory_root / "session").mkdir(parents=True, exist_ok=True)
        (self.memory_root / "traces").mkdir(parents=True, exist_ok=True)
        defaults = {
            "MEMORY.md": "# Personal Investment Memory\n\n## Risk Preference\n- Medium-term to long-term\n- Thesis first, technicals second\n- No impulse chasing\n",
            "profile.json": json.dumps(
                {
                    "investment_style": "mid_long_term",
                    "avoid": ["high_frequency_trading", "auto_execution"],
                    "preferred_sectors": ["L1", "DeFi", "Infra"],
                    "decision_style": "thesis_first_kline_assisted",
                    "risk_preference": "medium",
                },
                indent=2,
            )
            + "\n",
            "alerts.json": json.dumps({"items": []}, indent=2) + "\n",
            "watchlist.json": json.dumps({"assets": []}, indent=2) + "\n",
            "paper_portfolio.json": json.dumps({"cash": 10000.0, "positions": []}, indent=2) + "\n",
            "paper_orders.json": json.dumps([], indent=2) + "\n",
        }
        for filename, content in defaults.items():
            path = self.memory_root / filename
            if not path.exists():
                path.write_text(content, encoding="utf-8")
        session_path = self.memory_root / "session" / "current_session.json"
        if not session_path.exists():
            session_path.write_text(
                json.dumps(
                    {
                        "current_asset": None,
                        "last_intent": None,
                        "last_timeframes": [],
                        "last_report_type": None,
                        "recent_assets": [],
                        "current_task": None,
                        "last_skill": None,
                        "last_agent": None,
                    },
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )
