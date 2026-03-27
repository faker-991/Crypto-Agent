from pathlib import Path

from app.agents.research_agent import ResearchAgent
from app.services.scheduler_service import SchedulerService


def test_generate_report_writes_weekly_markdown_file(tmp_path: Path) -> None:
    (tmp_path / "watchlist.json").write_text(
        '{"assets":[{"symbol":"BTC","status":"core_watch","priority":1,"last_reviewed_at":"2026-03-17"},{"symbol":"ETH","status":"watch","priority":2,"last_reviewed_at":"2026-03-17"}]}',
        encoding="utf-8",
    )
    agent = ResearchAgent(memory_root=tmp_path)

    result = agent.execute(
        skill="generate_report",
        payload={
            "report_type": "weekly",
            "scope": "watchlist",
            "include_kline": True,
            "include_memory": True,
        },
    )

    assert result["report_type"] == "weekly"
    assert result["scope"] == "watchlist"
    report_path = Path(result["report_path"])
    assert report_path.exists()
    assert "BTC" in report_path.read_text(encoding="utf-8")


def test_scheduler_service_registers_weekly_report_job(tmp_path: Path) -> None:
    service = SchedulerService(memory_root=tmp_path)

    service.register_jobs()

    jobs = service.list_job_ids()
    assert "weekly-report" in jobs


def test_scheduler_weekly_job_runs_report_generation(tmp_path: Path) -> None:
    (tmp_path / "watchlist.json").write_text(
        '{"assets":[{"symbol":"SUI","status":"watch","priority":2,"last_reviewed_at":"2026-03-17"}]}',
        encoding="utf-8",
    )
    service = SchedulerService(memory_root=tmp_path)

    result = service.run_weekly_report_job()

    assert result["report_type"] == "weekly"
    assert Path(result["report_path"]).exists()
