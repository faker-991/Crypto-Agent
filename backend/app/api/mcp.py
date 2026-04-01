from fastapi import APIRouter, Depends

from app.clients.mcp_registry import MCPToolRegistry

router = APIRouter(prefix="/api/mcp", tags=["mcp"])


def get_mcp_registry() -> MCPToolRegistry:
    raise RuntimeError("mcp_registry dependency not configured")


@router.get("/servers")
def list_mcp_servers(registry: MCPToolRegistry = Depends(get_mcp_registry)) -> dict:
    return {"servers": registry.list_servers()}
