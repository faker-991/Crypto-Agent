from pathlib import Path

from app.services.asset_memory_service import AssetMemoryService
from app.services.memory_service import MemoryService


def test_asset_memory_service_reads_assets_thesis_first(tmp_path: Path) -> None:
    assets_dir = tmp_path / "assets"
    assets_dir.mkdir(parents=True)
    (assets_dir / "SUI.md").write_text("# SUI\n\nAsset thesis", encoding="utf-8")

    service = AssetMemoryService(tmp_path)

    thesis = service.get_thesis_content("SUI")

    assert "Asset thesis" in thesis


def test_asset_memory_service_falls_back_to_legacy_theses_path(tmp_path: Path) -> None:
    legacy_dir = tmp_path / "theses"
    legacy_dir.mkdir(parents=True)
    (legacy_dir / "SOL.md").write_text("# SOL\n\nLegacy thesis", encoding="utf-8")

    service = AssetMemoryService(tmp_path)

    thesis = service.get_thesis_content("SOL")

    assert "Legacy thesis" in thesis


def test_asset_memory_service_reads_asset_metadata_json(tmp_path: Path) -> None:
    assets_dir = tmp_path / "assets"
    assets_dir.mkdir(parents=True)
    (assets_dir / "BTC.json").write_text('{"asset":"BTC","status":"core_watch"}', encoding="utf-8")

    service = AssetMemoryService(tmp_path)

    metadata = service.get_asset_metadata("BTC")

    assert metadata["asset"] == "BTC"
    assert metadata["status"] == "core_watch"


def test_memory_service_get_thesis_prefers_assets_path(tmp_path: Path) -> None:
    assets_dir = tmp_path / "assets"
    legacy_dir = tmp_path / "theses"
    assets_dir.mkdir(parents=True)
    legacy_dir.mkdir(parents=True)
    (assets_dir / "ENA.md").write_text("# ENA\n\nAsset version", encoding="utf-8")
    (legacy_dir / "ENA.md").write_text("# ENA\n\nLegacy version", encoding="utf-8")

    service = MemoryService(tmp_path)

    thesis = service.get_thesis("ENA")

    assert thesis.symbol == "ENA"
    assert "Asset version" in thesis.content
