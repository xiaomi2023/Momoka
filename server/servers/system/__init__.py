"""
server/servers/system/__init__.py —— System 模块自动注册。

涵盖: system_command / change_directory / read_file / write_file / replace_file / read_sheet / py_exec
"""

from __future__ import annotations

from server.servers import ServerRegistration, register_server
from server.servers.system.tooldef import TOOL_DEFINITIONS, is_available
from server.servers.system import system as handler


# 自动注册 System 模块（使用 handlers 字典，推荐）
register_server(ServerRegistration(
    name='system',
    tool_definitions=TOOL_DEFINITIONS,
    handlers={
        'system_command': handler.system_command,
        'change_directory': handler.change_directory,
        'wait': handler.wait,
        'write_file': handler.write_file_tool,
        'replace_file': handler.replace_file,
        'read_file': handler.read_file,
        'read_sheet': handler.read_sheet,
        'py_exec': handler.py_exec,
    },
    condition=is_available,
))
