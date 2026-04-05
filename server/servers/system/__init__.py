"""
server/servers/system/__init__.py —— System 模块自动注册。

涵盖: system_command / change_directory / finish / read_file / edit_file / replace_file / read_sheet
"""

from __future__ import annotations

from server import ToolResult
from server.servers import ServerRegistration, register_server
from server.servers.system.tooldef import TOOL_DEFINITIONS, is_available
from server.servers.system import system as handler


def _handle(name: str, args: dict, ctx) -> ToolResult:
    """分发工具调用到具体处理器。"""
    match name:
        case 'finish':
            return handler.finish(args, ctx)
        case 'system_command':
            return handler.system_command(args, ctx)
        case 'change_directory':
            return handler.change_directory(args, ctx)
        case 'edit_file':
            return handler.edit_file_tool(args, ctx)
        case 'replace_file':
            return handler.replace_file(args, ctx)
        case 'read_file':
            return handler.read_file(args, ctx)
        case 'read_sheet':
            return handler.read_sheet(args, ctx)
        case _:
            return ToolResult(text=f'未知工具: {name}')


# 注册 System 模块
register_server(ServerRegistration(
    name='system',
    tool_definitions=TOOL_DEFINITIONS,
    handler=_handle,
    condition=is_available,
))
