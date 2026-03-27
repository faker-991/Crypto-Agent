from datetime import date
from pathlib import Path

from app.services.journal_memory_service import JournalMemoryService


def test_journal_memory_service_appends_entries_to_dated_file(tmp_path: Path) -> None:
    service = JournalMemoryService(tmp_path)

    service.append_entry(
        entry_date=date(2026, 3, 17),
        title="Added SUI To Watchlist",
        body="Catalyst quality improved and the thesis is still intact.",
    )

    path = tmp_path / "journal" / "2026-03-17.md"
    assert path.exists()
    content = path.read_text(encoding="utf-8")
    assert "Added SUI To Watchlist" in content
    assert "Catalyst quality improved" in content


def test_journal_memory_service_lists_recent_entries(tmp_path: Path) -> None:
    service = JournalMemoryService(tmp_path)
    service.append_entry(date(2026, 3, 16), "Old Entry", "Older note")
    service.append_entry(date(2026, 3, 17), "New Entry", "Latest note")

    entries = service.list_recent_entries(limit=5)

    assert len(entries) == 2
    assert entries[0]["date"] == "2026-03-17"
    assert entries[0]["title"] == "New Entry"
