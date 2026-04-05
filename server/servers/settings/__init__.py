"""
server/servers/settings/__init__.py —— Settings 模块自动注册。

涵盖: set_wait / set_read_limits
"""

from __future__ import annotations

from server.servers import ServerRegistration, register_server
from server.servers.settings.tooldef import TOOL_DEFINITIONS, is_available
from server.servers.settings import settings as handler


# 自动注册 Settings 模块（使用 handlers 字典，推荐）
register_server(ServerRegistration(
    name='settings',
    tool_definitions=TOOL_DEFINITIONS,
    handlers={
        'set_wait': handler.set_wait,
        'set_read_limits': handler.set_read_limits,
    },
    condition=is_available,
))
