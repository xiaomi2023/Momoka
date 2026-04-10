"""
server/servers/mcp/handler.py —— MCP tool unified handler.

All MCP tools are uniformly dispatched through this handler.
"""

from __future__ import annotations

from server.types import ToolResult, ToolContext
from server.servers.mcp.tooldef import is_mcp_available
from config import get_working_config


def handle_mcp_tool(name: str, args: dict, ctx: ToolContext) -> ToolResult:
    """MCP tool unified handler (serial)

    Args:
        name: Tool name
        args: Tool arguments
        ctx: Execution context

    Returns:
        Tool execution result
    """
    if not is_mcp_available():
        return ToolResult(
            text=f"MCP tool '{name}' not available",
            log_msg=f"MCP tool call failed: '{name}' - MCP not initialized",
            log_role='ERROR'
        )

    # Delayed import to avoid circular imports
    from server.servers.mcp import get_mcp_manager

    manager = get_mcp_manager()
    if manager is None:
        return ToolResult(
            text=f"MCP tool '{name}' not available: Manager not initialized",
            log_msg=f"MCP manager not initialized: {name}",
            log_role='ERROR'
        )

    # Find corresponding Server
    server_name = manager.get_server_for_tool(name)
    if server_name is None:
        return ToolResult(
            text=f"Unknown MCP tool: {name}",
            log_msg=f"MCP tool routing failed: {name}",
            log_role='ERROR'
        )

    # Synchronous call (uses independent thread internally for async)
    # Use working_config's wait parameter, consistent with other tools
    timeout = get_working_config().get('wait', 10)
    return manager.call_tool_sync(server_name, name, args, timeout=timeout)
