"""
server/servers/search/__init__.py — Search 模块自动注册。

涵盖: grep / glob
"""

from __future__ import annotations

from server.servers import ServerRegistration, register_server
from server.servers.search.tooldef import TOOL_DEFINITIONS, is_available
from server.servers.search import search as handler


# 自动注册 Search 模块（使用 handlers 字典，推荐）
register_server(ServerRegistration(
    name='search',
    tool_definitions=TOOL_DEFINITIONS,
    handlers={
        'grep': handler.grep,
        'glob': handler.glob,
    },
    condition=is_available,
))
