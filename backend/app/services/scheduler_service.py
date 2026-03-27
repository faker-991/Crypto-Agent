from pathlib import Path

from app.agents.research_agent import ResearchAgent

try:
    from apscheduler.schedulers.background import BackgroundScheduler
except Exception:  # pragma: no cover - optional dependency fallback for local test envs
    BackgroundScheduler = None


class _FallbackScheduler:
    def __init__(self) -> None:
        self.jobs: dict[str, dict] = {}

    def add_job(self, func, trigger: str, id: str, **kwargs) -> None:
        self.jobs[id] = {"func": func, "trigger": trigger, "kwargs": kwargs}

    def get_jobs(self) -> list:
        return [type("Job", (), {"id": job_id}) for job_id in self.jobs]

    def start(self) -> None:
        return None


class SchedulerService:
    def __init__(self, memory_root: Path) -> None:
        self.memory_root = memory_root
        self.research_agent = ResearchAgent(memory_root)
        self.scheduler = BackgroundScheduler() if BackgroundScheduler is not None else _FallbackScheduler()

    def register_jobs(self) -> None:
        self.scheduler.add_job(
            self.run_weekly_report_job,
            trigger="cron",
            day_of_week="sun",
            hour=18,
            minute=0,
            id="weekly-report",
            replace_existing=True,
        )

    def list_job_ids(self) -> list[str]:
        return [job.id for job in self.scheduler.get_jobs()]

    def run_weekly_report_job(self) -> dict:
        return self.research_agent.execute(
            skill="generate_report",
            payload={
                "report_type": "weekly",
                "scope": "watchlist",
                "include_kline": True,
                "include_memory": True,
            },
        )

    def start(self) -> None:
        self.register_jobs()
        self.scheduler.start()
