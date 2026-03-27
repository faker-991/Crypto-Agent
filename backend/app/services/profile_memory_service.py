import json
from pathlib import Path


class ProfileMemoryService:
    def __init__(self, memory_root: Path) -> None:
        self.profile_path = memory_root / "profile.json"

    def get_profile(self) -> dict:
        return json.loads(self.profile_path.read_text(encoding="utf-8"))

    def update_profile(self, payload: dict) -> dict:
        current = self.get_profile()
        current.update(payload)
        self.profile_path.write_text(json.dumps(current, indent=2) + "\n", encoding="utf-8")
        return current
