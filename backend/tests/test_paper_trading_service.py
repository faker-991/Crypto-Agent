from pathlib import Path

from app.schemas.paper_trading import PaperOrderCreate
from app.services.paper_trading_service import PaperTradingService


def test_bootstrap_creates_default_portfolio(tmp_path: Path) -> None:
    service = PaperTradingService(memory_root=tmp_path)

    portfolio = service.get_portfolio()

    assert portfolio.cash == 10000.0
    assert portfolio.positions == []
    assert (tmp_path / "paper_portfolio.json").exists()


def test_buy_order_updates_cash_and_position(tmp_path: Path) -> None:
    service = PaperTradingService(memory_root=tmp_path)

    portfolio = service.place_order(
        PaperOrderCreate(
            symbol="BTCUSDT",
            market_type="spot",
            side="buy",
            quantity=2,
            price=100,
        )
    )

    assert portfolio.cash == 9800.0
    assert len(portfolio.positions) == 1
    position = portfolio.positions[0]
    assert position.symbol == "BTCUSDT"
    assert position.quantity == 2
    assert position.average_entry_price == 100
    assert (tmp_path / "paper_orders.json").exists()


def test_sell_order_reduces_position_and_restores_cash(tmp_path: Path) -> None:
    service = PaperTradingService(memory_root=tmp_path)
    service.place_order(
        PaperOrderCreate(
            symbol="BTCUSDT",
            market_type="spot",
            side="buy",
            quantity=2,
            price=100,
        )
    )

    portfolio = service.place_order(
        PaperOrderCreate(
            symbol="BTCUSDT",
            market_type="spot",
            side="sell",
            quantity=1,
            price=120,
        )
    )

    assert portfolio.cash == 9920.0
    assert len(portfolio.positions) == 1
    assert portfolio.positions[0].quantity == 1
