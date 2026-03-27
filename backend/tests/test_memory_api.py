from datetime import date
from pathlib import Path

from app.api.memory import (
    read_assets,
    read_context_preview,
    read_journal,
    read_memory,
    read_profile,
)
from app.services.memory_service import MemoryService


def test_memory_api_reads_layered_memory_views(tmp_path: Path) -> None:
    memory_service = MemoryService(tmp_path)
    (tmp_path / "assets" / "SUI.md").write_text("# SUI\n\nCore thesis", encoding="utf-8")
    (tmp_path / "assets" / "SUI.json").write_text(
        '{"asset":"SUI","status":"watch","thesis_score":8}',
        encoding="utf-8",
    )
    memory_service.journal_memory_service.append_entry(
        date(2026, 3, 17),
        "Weekly Review",
        "SUI remains on the watchlist after the latest review.",
    )

    summary = read_memory(memory_service)
    profile = read_profile(memory_service)
    assets = read_assets(memory_service)
    journal = read_journal(memory_service=memory_service)
    context_preview = read_context_preview(
        kind="research",
        asset="SUI",
        intent="asset_due_diligence",
        memory_service=memory_service,
    )

    assert "Personal Investment Memory" in summary.content
    assert profile.profile["investment_style"] == "mid_long_term"
    assert assets.items[0].symbol == "SUI"
    assert assets.items[0].metadata["thesis_score"] == 8
    assert journal.items[0].title == "Weekly Review"
    assert context_preview.kind == "research"
    assert context_preview.context["asset"]["symbol"] == "SUI"
