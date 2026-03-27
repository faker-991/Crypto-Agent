from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import assets, conversations, memory, paper_trading, planner, research, trace, watchlist
from app.orchestrator.orchestrator_service import OrchestratorService
from app.services.answer_generation_service import AnswerGenerationService
from app.services.asset_discovery_service import AssetDiscoveryService
from app.services.conversation_service import ConversationService
from app.services.market_data_service import MarketDataService
from app.services.memory_service import MemoryService
from app.services.paper_trading_service import PaperTradingService
from app.services.scheduler_service import SchedulerService
from app.services.trace_log_service import TraceLogService


def create_app(memory_root: Path | None = None, enable_scheduler: bool = True) -> FastAPI:
    app = FastAPI(title="crypto-agent")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    resolved_memory_root = memory_root or Path(__file__).resolve().parents[2] / "memory"
    memory_service = MemoryService(resolved_memory_root)
    paper_trading_service = PaperTradingService(resolved_memory_root)
    market_data_service = MarketDataService()
    asset_discovery_service = AssetDiscoveryService(market_data_service=market_data_service)
    orchestrator_service = OrchestratorService(resolved_memory_root)
    trace_log_service = TraceLogService(resolved_memory_root)
    answer_generation_service = AnswerGenerationService()
    conversation_service = ConversationService(
        resolved_memory_root,
        orchestrator_service=orchestrator_service,
        trace_log_service=trace_log_service,
        answer_generation_service=answer_generation_service,
    )
    if enable_scheduler:
        scheduler_service = SchedulerService(resolved_memory_root)
        scheduler_service.register_jobs()

    app.state.conversation_service = conversation_service
    app.dependency_overrides[assets.get_asset_discovery_service] = lambda: asset_discovery_service
    app.dependency_overrides[assets.get_market_data_service] = lambda: market_data_service
    app.dependency_overrides[watchlist.get_memory_service] = lambda: memory_service
    app.dependency_overrides[memory.get_memory_service] = lambda: memory_service
    app.dependency_overrides[paper_trading.get_paper_trading_service] = (
        lambda: paper_trading_service
    )
    app.dependency_overrides[planner.get_orchestrator_service] = lambda: orchestrator_service
    app.dependency_overrides[research.get_market_data_service] = lambda: market_data_service
    app.dependency_overrides[trace.get_trace_log_service] = lambda: trace_log_service
    app.dependency_overrides[conversations.get_conversation_service] = lambda: conversation_service

    @app.get("/api/health")
    def healthcheck() -> dict[str, str]:
        return {"status": "ok"}

    app.include_router(assets.router)
    app.include_router(watchlist.router)
    app.include_router(memory.router)
    app.include_router(paper_trading.router)
    app.include_router(planner.router)
    app.include_router(research.router)
    app.include_router(trace.router)
    app.include_router(conversations.router)
    return app


app = create_app()
