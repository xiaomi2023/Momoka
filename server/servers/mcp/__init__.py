"""
server/servers/mcp/__init__.py —— MCP 模块自动注册。

提供全局 MCP 管理器实例的访问接口，并注册 MCP Server 模块。
"""

from __future__ import annotations

from server.servers import ServerRegistration, register_server
from server.servers.mcp import handler
from server.servers.mcp.tooldef import get_mcp_tool_definitions, is_mcp_available

# 全局管理器实例（由 Momoka 初始化时设置）
_manager = None


def get_mcp_manager():
    """获取全局 MCP 管理器实例

    Returns:
        MCPClientManager 实例或 None
    """
    return _manager


def set_mcp_manager(manager):
    """设置全局 MCP 管理器实例

    Args:
        manager: MCPClientManager 实例
    """
    global _manager
    _manager = manager


def _load_dynamic_tools() -> list[dict]:
    """动态加载工具定义（由 get_available_tools 调用）

    Returns:
        MCP 工具的 OpenAI 格式定义列表
    """
    if _manager is None:
        return []
    return _manager.get_openai_tool_definitions()


def _check_availability() -> bool:
    """检查 MCP 是否可用

    Returns:
        MCP 是否可用
    """
    try:
        import mcp  # noqa: F401
        return _manager is not None and len(_load_dynamic_tools()) > 0
    except ImportError:
        return False


# 注册 MCP Server 模块
register_server(ServerRegistration(
    name='mcp',
    tool_definitions=[],  # 占位，运行时动态获取
    dynamic_tool_definitions=_load_dynamic_tools,  # 动态工具定义生成函数
    condition=_check_availability,
    handler=handler.handle_mcp_tool,
))

# 导出动态工具定义接口
def get_dynamic_tool_definitions() -> list[dict]:
    """获取动态工具定义（供外部调用）

    Returns:
        MCP 工具的 OpenAI 格式定义列表
    """
    return _load_dynamic_tools()
