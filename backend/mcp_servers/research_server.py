"""Standalone Research MCP Server.

Run this script directly to expose web-search and page-fetch tools via the
MCP stdio protocol, compatible with any MCP-compliant host.

Usage:
    python mcp_servers/research_server.py
"""
from mcp.server.fastmcp import FastMCP

from app.agents.tools.research_tools import ResearchToolbox

mcp = FastMCP("research", description="网页搜索与内容抓取工具")
_toolbox = ResearchToolbox()


@mcp.tool()
def search_web(query: str) -> dict:
    """搜索互联网，返回与查询相关的页面列表。

    Args:
        query: 搜索关键词
    """
    return _toolbox.search_web(query)


@mcp.tool()
def fetch_page(url: str) -> dict:
    """抓取指定 URL 的页面正文内容。

    Args:
        url: 目标页面 URL
    """
    return _toolbox.fetch_page(url)


if __name__ == "__main__":
    mcp.run()
