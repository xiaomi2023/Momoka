"""
server/servers/__init__.py —— Server 模块自动注册接口。

提供自动注册机制，新模块只需在 __init__.py 中调用 register_server() 即可自动注册，
无需修改 tool_registry.py 和 router.py。

用法示例（server/servers/my_module/__init__.py）：
    from server.servers import ServerRegistration, register_server
    from server.servers.my_module.tooldef import TOOL_DEFINITIONS
    from server.servers.my_module import handler

    def _handle(name: str, args: dict, ctx) -> ToolResult:
        match name:
            case 'my_tool': return handler.my_tool(args, ctx)
            case _: return ToolResult(text=f'未知工具: {name}')

    register_server(ServerRegistration(
        name='my_module',
        tool_definitions=TOOL_DEFINITIONS,
        handler=_handle,
    ))
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from server import ToolResult, ToolContext


@dataclass
class ServerRegistration:
    """Server 模块注册信息。
    
    Attributes:
        name: 模块名称（唯一标识）
        tool_definitions: 工具定义列表（JSON Schema）
        handler: 工具处理函数，接收 (name, args, ctx) 返回 ToolResult
        condition: 可用性检查函数，返回 bool，None 表示始终可用
    """
    name: str
    tool_definitions: list[dict]
    handler: Callable[[str, dict, ToolContext], ToolResult]
    condition: Callable[[], bool] | None = None


# 全局注册表: name -> ServerRegistration
_registered_servers: dict[str, ServerRegistration] = {}


def register_server(reg: ServerRegistration) -> None:
    """注册一个 Server 模块。
    
    Args:
        reg: 注册信息
        
    Raises:
        ValueError: 如果同名模块已注册
    """
    if reg.name in _registered_servers:
        raise ValueError(f"Server module '{reg.name}' is already registered")
    _registered_servers[reg.name] = reg


def get_registered_servers() -> dict[str, ServerRegistration]:
    """获取所有已注册的 Server 模块（副本）。"""
    return _registered_servers.copy()


def get_server(name: str) -> ServerRegistration | None:
    """获取指定名称的 Server 注册信息。
    
    Args:
        name: 模块名称
        
    Returns:
        ServerRegistration: 如果找到
        None: 如果未找到
    """
    return _registered_servers.get(name)


def get_available_tools() -> list[dict]:
    """获取所有可用 Server 的工具定义列表。
    
    Returns:
        所有可用工具定义的总列表
    """
    tools: list[dict] = []
    for reg in _registered_servers.values():
        if reg.condition is None or reg.condition():
            tools.extend(reg.tool_definitions)
    return tools


def dispatch_tool(name: str, args: dict, ctx: ToolContext) -> ToolResult | None:
    """分发工具调用到对应的 Server 模块。
    
    遍历所有已注册的 Server，找到能处理该工具的 Server 并执行。
    
    Args:
        name: 工具名称
        args: 工具参数
        ctx: 执行上下文
        
    Returns:
        ToolResult: 找到并执行成功
        None: 没有 Server 能处理该工具
    """
    for reg in _registered_servers.values():
        # 检查可用性
        if reg.condition is not None and not reg.condition():
            continue
        
        # 检查该 Server 是否支持此工具
        tool_names = {
            t['function']['name'] 
            for t in reg.tool_definitions 
            if 'function' in t and 'name' in t['function']
        }
        
        if name in tool_names:
            return reg.handler(name, args, ctx)
    
    return None


def get_all_tool_names() -> list[str]:
    """获取所有已注册的工具名称。
    
    Returns:
        所有工具名称列表
    """
    names: list[str] = []
    for reg in _registered_servers.values():
        for tool in reg.tool_definitions:
            if 'function' in tool and 'name' in tool['function']:
                names.append(tool['function']['name'])
    return names


def clear_registrations() -> None:
    """清除所有注册（主要用于测试）。"""
    _registered_servers.clear()
