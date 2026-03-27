import json
from pathlib import Path

from app.schemas.paper_trading import (
    PaperOrderCreate,
    PaperOrderRecord,
    PaperPortfolio,
    PaperPosition,
)
from app.services.bootstrap_service import BootstrapService


class PaperTradingService:
    def __init__(self, memory_root: Path) -> None:
        self.memory_root = memory_root
        BootstrapService(memory_root).ensure_files()

    def get_portfolio(self) -> PaperPortfolio:
        payload = json.loads((self.memory_root / "paper_portfolio.json").read_text(encoding="utf-8"))
        return PaperPortfolio.model_validate(payload)

    def place_order(self, order: PaperOrderCreate) -> PaperPortfolio:
        portfolio = self.get_portfolio()
        notional = order.quantity * order.price
        if order.side.lower() == "buy":
            portfolio.cash -= notional
            position = next(
                (
                    item
                    for item in portfolio.positions
                    if item.symbol == order.symbol and item.market_type == order.market_type
                ),
                None,
            )
            if position:
                total_quantity = position.quantity + order.quantity
                position.average_entry_price = (
                    (position.average_entry_price * position.quantity) + notional
                ) / total_quantity
                position.quantity = total_quantity
                position.last_price = order.price
            else:
                portfolio.positions.append(
                    PaperPosition(
                        symbol=order.symbol,
                        market_type=order.market_type,
                        quantity=order.quantity,
                        average_entry_price=order.price,
                        last_price=order.price,
                    )
                )
        elif order.side.lower() == "sell":
            portfolio.cash += notional
            position = next(
                (
                    item
                    for item in portfolio.positions
                    if item.symbol == order.symbol and item.market_type == order.market_type
                ),
                None,
            )
            if position:
                position.quantity -= order.quantity
                position.last_price = order.price
                if position.quantity <= 0:
                    portfolio.positions = [
                        item
                        for item in portfolio.positions
                        if not (
                            item.symbol == order.symbol and item.market_type == order.market_type
                        )
                    ]
        self._write_json("paper_portfolio.json", portfolio.model_dump())
        self._append_order(
            PaperOrderRecord(
                symbol=order.symbol,
                market_type=order.market_type,
                side=order.side,
                quantity=order.quantity,
                price=order.price,
                notional=notional,
            )
        )
        return portfolio

    def _append_order(self, order: PaperOrderRecord) -> None:
        path = self.memory_root / "paper_orders.json"
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload.append(order.model_dump())
        path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    def _write_json(self, filename: str, payload: dict) -> None:
        (self.memory_root / filename).write_text(
            json.dumps(payload, indent=2) + "\n",
            encoding="utf-8",
        )
