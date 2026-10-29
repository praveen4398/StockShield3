"""MCP Client wrapper providing typed tool calls, real stdio session transport, and validation."""

import json
import os
import sys
import time
from typing import Any, Dict, Optional

from mcp.client.session import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

from stockshield.mcp.server import (
    compute_financial_ratios,
    get_historical_market_data,
    search_financial_document,
)


class MCPToolClient:
    """Client for calling MCP tools supporting real stdio subprocess ClientSession and in-process execution."""

    def __init__(self, server_script: Optional[str] = None):
        self.server_script = server_script or "src/stockshield/mcp/server.py"
        self._tool_registry = {
            "get_historical_market_data": get_historical_market_data,
            "compute_financial_ratios": compute_financial_ratios,
            "search_financial_document": search_financial_document,
        }

    async def call_tool_stdio(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Call an MCP tool through a genuine MCP ClientSession over stdio subprocess."""
        start_time = time.perf_counter()
        env = dict(os.environ)
        env["PYTHONPATH"] = "src"

        server_params = StdioServerParameters(
            command=sys.executable,
            args=[self.server_script],
            env=env,
        )

        try:
            async with stdio_client(server_params) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    call_result = await session.call_tool(tool_name, arguments)
                    duration_ms = (time.perf_counter() - start_time) * 1000

                    # Parse MCP CallToolResult content
                    raw_text = call_result.content[0].text if call_result.content else "{}"
                    parsed_result = json.loads(raw_text)

                    return {
                        "status": "success",
                        "transport": "mcp_stdio_session",
                        "tool_name": tool_name,
                        "duration_ms": round(duration_ms, 2),
                        "result": parsed_result,
                    }
        except Exception as e:
            duration_ms = (time.perf_counter() - start_time) * 1000
            return {
                "status": "error",
                "transport": "mcp_stdio_session",
                "tool_name": tool_name,
                "duration_ms": round(duration_ms, 2),
                "error": str(e),
                "result": None,
            }

    async def call_tool(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
        transport: str = "in_process",
    ) -> Dict[str, Any]:
        """Call an MCP tool with explicit transport selection."""
        if transport == "stdio":
            return await self.call_tool_stdio(tool_name, arguments)

        start_time = time.perf_counter()
        if tool_name not in self._tool_registry:
            duration_ms = (time.perf_counter() - start_time) * 1000
            return {
                "status": "error",
                "transport": "in_process",
                "error": f"Tool '{tool_name}' not registered in MCP server.",
                "duration_ms": duration_ms,
                "result": None,
            }

        fn = self._tool_registry[tool_name]
        try:
            raw_result = fn(**arguments)
            duration_ms = (time.perf_counter() - start_time) * 1000
            return {
                "status": "success",
                "transport": "in_process",
                "tool_name": tool_name,
                "duration_ms": round(duration_ms, 2),
                "result": raw_result,
            }
        except Exception as e:
            duration_ms = (time.perf_counter() - start_time) * 1000
            return {
                "status": "error",
                "transport": "in_process",
                "tool_name": tool_name,
                "duration_ms": round(duration_ms, 2),
                "error": str(e),
                "result": None,
            }
