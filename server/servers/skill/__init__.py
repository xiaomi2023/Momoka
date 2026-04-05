"""
server/servers/skill/__init__.py —— Skill 模块自动注册。

涵盖: get_skill
"""

from __future__ import annotations

from server import ToolResult
from server.servers import ServerRegistration, register_server
from server.servers.skill.tooldef import TOOL_DEFINITIONS, is_available
from server.servers.skill import skill as handler


def _handle(name: str, args: dict, ctx) -> ToolResult:
    """分发工具调用到具体处理器。"""
    match name:
        case 'get_skill':
            return handler.get_skill(args, ctx)
        case _:
            return ToolResult(text=f'未知工具: {name}')


# 注册 Skill 模块
register_server(ServerRegistration(
    name='skill',
    tool_definitions=TOOL_DEFINITIONS,
    handler=_handle,
    condition=is_available,
))
