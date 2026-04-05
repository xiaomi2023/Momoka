"""
server/servers/user/__init__.py —— User 交互模块自动注册。

涵盖: ask_user / set_todolist / ask_option
"""

from __future__ import annotations

from server.servers import ServerRegistration, register_server
from server.servers.user.tooldef import TOOL_DEFINITIONS, is_available
from server.servers.user import user as handler


# 自动注册 User 模块（使用 handlers 字典，推荐）
register_server(ServerRegistration(
    name='user',
    tool_definitions=TOOL_DEFINITIONS,
    handlers={
        'ask_user': handler.ask_user,
        'set_todolist': handler.set_todolist,
        'ask_option': handler.ask_option,
    },
    condition=is_available,
))
