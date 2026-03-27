import json
from pathlib import Path


class AssetMemoryService:
    def __init__(self, memory_root: Path) -> None:
        self.memory_root = memory_root
        self.assets_root = memory_root / "assets"
        self.legacy_theses_root = memory_root / "theses"
        self.assets_root.mkdir(parents=True, exist_ok=True)
        self.legacy_theses_root.mkdir(parents=True, exist_ok=True)

    def get_thesis_content(self, symbol: str) -> str:
        symbol = symbol.upper()
        asset_path = self.assets_root / f"{symbol}.md"
        legacy_path = self.legacy_theses_root / f"{symbol}.md"
        if asset_path.exists():
            return asset_path.read_text(encoding="utf-8")
        if legacy_path.exists():
            return legacy_path.read_text(encoding="utf-8")
        return ""

    def get_asset_metadata(self, symbol: str) -> dict:
        symbol = symbol.upper()
        json_path = self.assets_root / f"{symbol}.json"
        if not json_path.exists():
            return {}
        return json.loads(json_path.read_text(encoding="utf-8"))
