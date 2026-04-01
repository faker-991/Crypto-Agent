"""Standalone Binance MCP Server.

Run this script directly to expose Binance market data tools via the MCP
stdio protocol, compatible with any MCP-compliant host.

Usage:
    python mcp_servers/binance_server.py
"""
from mcp.server.fastmcp import FastMCP

from app.clients.binance_market_adapter import BinanceMarketAdapter

mcp = FastMCP("binance", description="Binance 实时行情工具")
_adapter = BinanceMarketAdapter()


@mcp.tool()
def get_klines(
    symbol: str,
    interval: str,
    market_type: str = "spot",
    limit: int = 120,
) -> dict:
    """从 Binance 获取 K 线数据，支持现货和合约市场。

    Args:
        symbol: 交易对，例如 BTCUSDT
        interval: K 线周期，例如 1d、4h、1h
        market_type: 市场类型，spot 或 futures
        limit: 返回 K 线数量（最多 500）
    """
    klines = _adapter.fetch_public_klines(symbol, interval, market_type, limit)
    return {
        "candles": [list(k) for k in klines],
        "market_type": market_type,
        "source": "binance",
    }


@mcp.tool()
def get_ticker(symbol: str, market_type: str = "spot") -> dict:
    """获取 Binance 实时报价（最新价、涨跌幅、成交量）。

    Args:
        symbol: 交易对，例如 BTCUSDT
        market_type: 市场类型，spot 或 futures
    """
    if market_type == "futures":
        return _adapter.fetch_futures_ticker(symbol)
    return _adapter.fetch_spot_ticker(symbol)


if __name__ == "__main__":
    mcp.run()
