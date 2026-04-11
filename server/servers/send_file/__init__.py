"""
server/servers/send_file/__init__.py — Send File 模块自动注册。

仅在飞书或 Discord 模式下可用。
"""

from __future__ import annotations

from server.servers import ServerRegistration, register_server
from server.servers.send_file.tooldef import TOOL_DEFINITIONS, is_available
from server.servers.send_file import send_file as handler


# 自动注册 Send File 模块
register_server(ServerRegistration(
    name='send_file',
    tool_definitions=TOOL_DEFINITIONS,
    handlers={
        'send_file': handler.send_file,
    },
    condition=is_available,
))
