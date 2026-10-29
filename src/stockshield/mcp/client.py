"""MCP Client wrapper providing typed tool calls, latency metrics, and validation."""

import time
from typing import Any, Dict

from stockshield.mcp.server import (
    compute_financial_ratios,
    get_historical_market_data,
    search_financial_document,
)


class MCPToolClient:
    """Client for calling MCP tools with execution metrics and structured validation."""

    def __init__(self):
        self._tool_registry = {
            "get_historical_market_data": get_historical_market_data,
            "compute_financial_ratios": compute_financial_ratios,
            "search_financial_document": search_financial_document,
        }

    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Call an MCP tool, measuring exact latency and handling failures safely."""
        start_time = time.perf_counter()
        if tool_name not in self._tool_registry:
            duration_ms = (time.perf_counter() - start_time) * 1000
            return {
                "status": "error",
                "error": f"Tool '{tool_name}' not registered in MCP server.",
                "duration_ms": duration_ms,
                "result": None,
            }

        fn = self._tool_registry[tool_name]
        try:
            # Execute tool
            raw_result = fn(**arguments)
            duration_ms = (time.perf_counter() - start_time) * 1000
            return {
                "status": "success",
                "tool_name": tool_name,
                "duration_ms": round(duration_ms, 2),
                "result": raw_result,
            }
        except Exception as e:
            duration_ms = (time.perf_counter() - start_time) * 1000
            return {
                "status": "error",
                "tool_name": tool_name,
                "duration_ms": round(duration_ms, 2),
                "error": str(e),
                "result": None,
            }
