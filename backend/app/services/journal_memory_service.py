from datetime import date
from pathlib import Path


class JournalMemoryService:
    def __init__(self, memory_root: Path) -> None:
        self.journal_root = memory_root / "journal"
        self.journal_root.mkdir(parents=True, exist_ok=True)

    def append_entry(self, entry_date: date, title: str, body: str) -> Path:
        path = self.journal_root / f"{entry_date.isoformat()}.md"
        prefix = "" if not path.exists() else "\n"
        path.write_text(
            path.read_text(encoding="utf-8") + f"{prefix}## {title}\n\n{body}\n"
            if path.exists()
            else f"# Journal {entry_date.isoformat()}\n\n## {title}\n\n{body}\n",
            encoding="utf-8",
        )
        return path

    def read_day(self, entry_date: date) -> str:
        path = self.journal_root / f"{entry_date.isoformat()}.md"
        return path.read_text(encoding="utf-8") if path.exists() else ""

    def list_recent_entries(self, limit: int = 10) -> list[dict]:
        items = []
        paths = sorted(self.journal_root.glob("*.md"), reverse=True)[:limit]
        for path in paths:
            content = path.read_text(encoding="utf-8")
            title = ""
            for line in content.splitlines():
                if line.startswith("## "):
                    title = line[3:].strip()
                    break
            items.append(
                {
                    "date": path.stem,
                    "title": title,
                    "path": str(path),
                }
            )
        return items
