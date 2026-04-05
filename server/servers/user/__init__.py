"""
server/servers/user/__init__.py —— User 交互模块自动注册。

涵盖: ask_user / set_todolist / ask_option
"""

from __future__ import annotations

from server import ToolResult
from server.servers import ServerRegistration, register_server
from server.servers.user.tooldef import TOOL_DEFINITIONS, is_available
from server.servers.user import user as handler


def _handle(name: str, args: dict, ctx) -> ToolResult:
    """分发工具调用到具体处理器。"""
    match name:
        case 'ask_user':
            return handler.ask_user(args, ctx)
        case 'set_todolist':
            return handler.set_todolist(args, ctx)
        case 'ask_option':
            return handler.ask_option(args, ctx)
        case _:
            return ToolResult(text=f'未知工具: {name}')


# 注册 User 模块
register_server(ServerRegistration(
    name='user',
    tool_definitions=TOOL_DEFINITIONS,
    handler=_handle,
    condition=is_available,
))
