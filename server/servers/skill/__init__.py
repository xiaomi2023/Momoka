"""
server/servers/skill/__init__.py —— Skill 模块自动注册。

涵盖: get_skill
"""

from __future__ import annotations

from server.servers import ServerRegistration, register_server
from server.servers.skill.tooldef import TOOL_DEFINITIONS, is_available
from server.servers.skill import skill as handler


# 自动注册 Skill 模块（使用 handlers 字典，推荐）
register_server(ServerRegistration(
    name='skill',
    tool_definitions=TOOL_DEFINITIONS,
    handlers={
        'get_skill': handler.get_skill,
    },
    condition=is_available,
))
