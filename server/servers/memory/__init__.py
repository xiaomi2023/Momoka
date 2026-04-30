"""
server/servers/memory/__init__.py —— Memory 模块自动注册。

涵盖: memorize / recall
依赖 config.json 中的 memory 开关。
"""

from __future__ import annotations

from server.servers import ServerRegistration, register_server
from server.servers.memory.tooldef import TOOL_DEFINITIONS, is_available
from server.servers.memory import memory as handler


# 自动注册 Memory 模块（使用 handlers 字典，推荐）
register_server(ServerRegistration(
    name='memory',
    tool_definitions=TOOL_DEFINITIONS,
    handlers={
        'memorize': handler.memorize,
        'recall': handler.recall,
    },
    condition=is_available,
))
