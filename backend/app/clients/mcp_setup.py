from app.clients.binance_market_adapter import BinanceMarketAdapter
from app.clients.mcp_registry import MCPToolRegistry
from app.agents.tools.research_tools import ResearchToolbox


def build_mcp_registry() -> MCPToolRegistry:
    registry = MCPToolRegistry()

    adapter = BinanceMarketAdapter()

    def binance_handler(tool: str, args: dict) -> dict:
        if tool == "get_klines":
            klines = adapter.fetch_public_klines(
                args["symbol"],
                args["interval"],
                args.get("market_type", "spot"),
                args.get("limit", 120),
            )
            return {
                "candles": [list(k) for k in klines],
                "market_type": args.get("market_type", "spot"),
                "source": "binance",
            }
        if tool == "get_ticker":
            if args.get("market_type") == "futures":
                return adapter.fetch_futures_ticker(args["symbol"])
            return adapter.fetch_spot_ticker(args["symbol"])
        raise ValueError(f"Unknown binance tool: {tool!r}")

    registry.register(
        "binance",
        "Binance 实时行情工具",
        [
            {
                "name": "get_klines",
                "description": "从 Binance 获取 K 线数据，支持现货和合约市场",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "symbol": {"type": "string", "description": "交易对，例如 BTCUSDT"},
                        "interval": {"type": "string", "description": "K 线周期，例如 1d、4h"},
                        "market_type": {"type": "string", "default": "spot", "description": "市场类型：spot 或 futures"},
                        "limit": {"type": "integer", "default": 120, "description": "返回 K 线数量"},
                    },
                    "required": ["symbol", "interval"],
                },
            },
            {
                "name": "get_ticker",
                "description": "获取 Binance 实时报价（最新价、涨跌幅、成交量）",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "symbol": {"type": "string", "description": "交易对，例如 BTCUSDT"},
                        "market_type": {"type": "string", "default": "spot", "description": "市场类型：spot 或 futures"},
                    },
                    "required": ["symbol"],
                },
            },
        ],
        binance_handler,
    )

    _direct_toolbox = ResearchToolbox()

    def research_handler(tool: str, args: dict) -> dict:
        if tool == "search_web":
            return _direct_toolbox.search_web(args["query"])
        if tool == "fetch_page":
            return _direct_toolbox.fetch_page(args["url"])
        raise ValueError(f"Unknown research tool: {tool!r}")

    registry.register(
        "research",
        "网页搜索与内容抓取工具",
        [
            {
                "name": "search_web",
                "description": "搜索互联网，返回与查询相关的页面列表",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "搜索关键词"},
                    },
                    "required": ["query"],
                },
            },
            {
                "name": "fetch_page",
                "description": "抓取指定 URL 的页面正文内容",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "url": {"type": "string", "description": "目标页面 URL"},
                    },
                    "required": ["url"],
                },
            },
        ],
        research_handler,
    )

    return registry
