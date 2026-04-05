"""
server/servers/__init__.py —— Server 模块自动注册接口。

提供自动注册机制，新模块只需在 __init__.py 中调用 register_server() 即可自动注册，
无需修改 tool_registry.py 和 router.py。

用法示例（server/servers/my_module/__init__.py）：
    from server.servers import ServerRegistration, register_server
    from server.servers.my_module.tooldef import TOOL_DEFINITIONS
    from server.servers.my_module import handler

    register_server(ServerRegistration(
        name='my_module',
        tool_definitions=TOOL_DEFINITIONS,
        handlers={
            'my_tool': handler.my_tool,
            'another_tool': handler.another_tool,
        },
    ))
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

import dataclasses

from server import ToolResult, ToolContext, UnknownToolError


@dataclass
class ServerRegistration:
    """Server 模块注册信息。
    
    Attributes:
        name: 模块名称（唯一标识）
        tool_definitions: 工具定义列表（JSON Schema）
        handler: 工具处理函数，接收 (name, args, ctx) 返回 ToolResult
                 与 handlers 二选一，优先使用 handlers
        condition: 可用性检查函数，返回 bool，None 表示始终可用
        handlers: 工具名到处理函数的字典，简化注册方式
                  处理函数签名: (args: dict, ctx: ToolContext) -> ToolResult
    """
    name: str
    tool_definitions: list[dict]
    handler: Callable[[str, dict, ToolContext], ToolResult] | None = None
    condition: Callable[[], bool] | None = None
    handlers: dict[str, Callable[[dict, ToolContext], ToolResult]] | None = None


# 全局注册表: name -> ServerRegistration
_registered_servers: dict[str, ServerRegistration] = {}


def _create_handler_from_dict(
    handlers: dict[str, Callable[[dict, ToolContext], ToolResult]]
) -> Callable[[str, dict, ToolContext], ToolResult]:
    """从 handlers 字典创建 handler 函数。
    
    生成的 handler 会在找不到工具时抛出 UnknownToolError，
    由 dispatch_tool 统一捕获并转换为 ToolResult。
    """
    def handler(name: str, args: dict, ctx: ToolContext) -> ToolResult:
        func = handlers.get(name)
        if func is None:
            raise UnknownToolError(name)
        return func(args, ctx)
    return handler


def register_server(reg: ServerRegistration) -> None:
    """注册一个 Server 模块。
    
    Args:
        reg: 注册信息，提供 handlers 字典或 handler 函数均可
        
    Raises:
        ValueError: 如果同名模块已注册，或既未提供 handler 也未提供 handlers
    """
    if reg.name in _registered_servers:
        raise ValueError(f"Server module '{reg.name}' is already registered")
    
    # 如果提供了 handlers 字典，自动生成 handler 函数
    if reg.handlers is not None:
        reg = dataclasses.replace(
            reg,
            handler=_create_handler_from_dict(reg.handlers)
        )
    
    # 验证 handler 已提供
    if reg.handler is None:
        raise ValueError(f"Server module '{reg.name}' must provide either 'handler' or 'handlers'")
    
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
    如果 handler 抛出 UnknownToolError，统一转换为 Unknown Tool 错误结果。
    
    Args:
        name: 工具名称
        args: 工具参数
        ctx: 执行上下文
        
    Returns:
        ToolResult: 找到并执行成功，或执行失败返回错误信息
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
            try:
                return reg.handler(name, args, ctx)
            except UnknownToolError:
                return ToolResult(text=f'Unknown Tool: {name}')
    
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
