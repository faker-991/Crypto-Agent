from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable


@dataclass
class MCPToolCall:
    server: str
    tool: str
    input: dict
    output: dict
    start_ts: str
    duration_ms: float
    error: str | None = None


class MCPToolRegistry:
    def __init__(self) -> None:
        self._servers: dict[str, dict] = {}

    def register(
        self,
        name: str,
        description: str,
        tools: list[dict],
        handler: Callable[[str, dict], Any],
    ) -> None:
        self._servers[name] = {
            "name": name,
            "description": description,
            "tools": tools,
            "handler": handler,
        }

    def list_servers(self) -> list[dict]:
        return [
            {"name": s["name"], "description": s["description"], "tools": s["tools"]}
            for s in self._servers.values()
        ]

    def call_tool(self, server: str, tool: str, args: dict) -> MCPToolCall:
        start = datetime.now(timezone.utc)
        start_ts = start.isoformat().replace("+00:00", "Z")
        s = self._servers.get(server)
        error: str | None = None
        output: dict = {}
        try:
            if s is None:
                raise KeyError(f"Unknown MCP server: {server!r}")
            result = s["handler"](tool, args)
            output = result if isinstance(result, dict) else {"result": result}
        except Exception as exc:
            error = str(exc)
        end = datetime.now(timezone.utc)
        duration_ms = (end - start).total_seconds() * 1000
        return MCPToolCall(
            server=server,
            tool=tool,
            input=args,
            output=output,
            start_ts=start_ts,
            duration_ms=duration_ms,
            error=error,
        )
