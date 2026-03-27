import json
from pathlib import Path

from app.services.bootstrap_service import BootstrapService
from app.services.profile_memory_service import ProfileMemoryService


def test_bootstrap_creates_memory_architecture_files(tmp_path: Path) -> None:
    BootstrapService(tmp_path).ensure_files()

    assert (tmp_path / "profile.json").exists()
    assert (tmp_path / "alerts.json").exists()
    assert (tmp_path / "assets").exists()
    assert (tmp_path / "journal").exists()
    assert (tmp_path / "reports" / "weekly").exists()
    assert (tmp_path / "traces").exists()

    profile = json.loads((tmp_path / "profile.json").read_text(encoding="utf-8"))
    alerts = json.loads((tmp_path / "alerts.json").read_text(encoding="utf-8"))
    assert profile["investment_style"] == "mid_long_term"
    assert alerts["items"] == []


def test_profile_memory_service_reads_default_profile(tmp_path: Path) -> None:
    BootstrapService(tmp_path).ensure_files()
    service = ProfileMemoryService(tmp_path)

    profile = service.get_profile()

    assert profile["investment_style"] == "mid_long_term"
    assert profile["risk_preference"] == "medium"
