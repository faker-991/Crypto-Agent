from pathlib import Path

from app.services.binance_skill_registry import BinanceSkillRegistry


def test_registry_discovers_installed_binance_skills(tmp_path: Path) -> None:
    skill_root = tmp_path / "skills"
    (skill_root / "spot").mkdir(parents=True)
    (skill_root / "spot" / "SKILL.md").write_text("---\nname: spot\n---\n", encoding="utf-8")
    (skill_root / "derivatives-trading-usds-futures").mkdir(parents=True)
    (skill_root / "derivatives-trading-usds-futures" / "SKILL.md").write_text(
        "---\nname: derivatives-trading-usds-futures\n---\n",
        encoding="utf-8",
    )

    registry = BinanceSkillRegistry(skill_roots=[skill_root])

    installed = registry.get_installed_skills()

    assert set(installed) == {"spot", "derivatives-trading-usds-futures"}
    assert registry.resolve_market_key("futures") == "derivatives-trading-usds-futures"


def test_registry_returns_endpoint_spec_for_known_skill() -> None:
    registry = BinanceSkillRegistry(skill_roots=[])

    spec = registry.get_spec("spot")

    assert spec["base_url"] == "https://api.binance.com"
    assert spec["public_endpoints"]["klines"] == "/api/v3/klines"
