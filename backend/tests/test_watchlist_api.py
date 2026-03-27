from pathlib import Path

from app.api.memory import read_thesis
from app.api.watchlist import add_watchlist_item, read_watchlist, remove_watchlist_item
from app.schemas.watchlist import WatchlistAddRequest, WatchlistRemoveRequest
from app.services.memory_service import MemoryService


def test_get_watchlist_returns_bootstrapped_file(tmp_path: Path) -> None:
    memory_service = MemoryService(tmp_path)

    payload = read_watchlist(memory_service)

    assert payload.model_dump() == {"assets": []}
    assert (tmp_path / "watchlist.json").exists()


def test_add_watchlist_item_persists_to_disk(tmp_path: Path) -> None:
    memory_service = MemoryService(tmp_path)

    payload = add_watchlist_item(
        WatchlistAddRequest(symbol="BTC", status="core_watch", priority=1),
        memory_service,
    )

    assert payload.assets[0].symbol == "BTC"
    stored = (tmp_path / "watchlist.json").read_text(encoding="utf-8")
    assert '"symbol": "BTC"' in stored


def test_get_thesis_returns_markdown_contents(tmp_path: Path) -> None:
    theses_dir = tmp_path / "theses"
    theses_dir.mkdir(parents=True)
    (theses_dir / "BTC.md").write_text("# BTC\n\nLong-term thesis", encoding="utf-8")

    memory_service = MemoryService(tmp_path)

    response = read_thesis("BTC", memory_service)

    assert response.content == "# BTC\n\nLong-term thesis"


def test_remove_watchlist_item_persists_to_disk(tmp_path: Path) -> None:
    memory_service = MemoryService(tmp_path)
    add_watchlist_item(
        WatchlistAddRequest(symbol="BTC", status="core_watch", priority=1),
        memory_service,
    )

    payload = remove_watchlist_item(
        WatchlistRemoveRequest(symbol="BTC"),
        memory_service,
    )

    assert payload.assets == []
    stored = (tmp_path / "watchlist.json").read_text(encoding="utf-8")
    assert '"assets": []' in stored
