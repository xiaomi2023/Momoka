"""
server/servers/mcp/tooldef.py —— MCP 工具定义生成。

动态获取 MCP 工具定义，由 ServerRegistration 调用。
"""

from __future__ import annotations


def get_mcp_tool_definitions() -> list[dict]:
    """动态获取 MCP 工具定义（由 ServerRegistration 调用）

    Returns:
        MCP 工具的 OpenAI 格式定义列表
    """
    # 延迟导入以避免循环导入
    from server.servers.mcp import get_mcp_manager

    manager = get_mcp_manager()
    if manager is None:
        return []
    return manager.get_openai_tool_definitions()


def is_mcp_available() -> bool:
    """检查 MCP 是否可用

    Returns:
        MCP 是否可用
    """
    try:
        import mcp  # noqa: F401
        # 延迟导入以避免循环导入
        from server.servers.mcp import get_mcp_manager
        manager = get_mcp_manager()
        return manager is not None and len(manager.get_openai_tool_definitions()) > 0
    except ImportError:
        return False
