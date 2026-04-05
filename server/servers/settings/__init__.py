"""
server/servers/settings/__init__.py —— Settings 模块自动注册。

涵盖: set_wait / set_read_limits
"""

from __future__ import annotations

from server import ToolResult
from server.servers import ServerRegistration, register_server
from server.servers.settings.tooldef import TOOL_DEFINITIONS, is_available
from server.servers.settings import settings as handler


def _handle(name: str, args: dict, ctx) -> ToolResult:
    """分发工具调用到具体处理器。"""
    match name:
        case 'set_wait':
            return handler.set_wait(args, ctx)
        case 'set_read_limits':
            return handler.set_read_limits(args, ctx)
        case _:
            return ToolResult(text=f'未知工具: {name}')


# 注册 Settings 模块
register_server(ServerRegistration(
    name='settings',
    tool_definitions=TOOL_DEFINITIONS,
    handler=_handle,
    condition=is_available,
))
