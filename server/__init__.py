"""Server package — Tool execution and browser automation."""

from __future__ import annotations

# 从 types.py 导入核心类型（避免循环导入）
from server.types import ToolResult, ToolContext, UnknownToolError

# 延迟导入函数（避免循环依赖）
from server.router import execute_tool_calls, _execute_tool
from server.servers.system.system import (
    _system_command_impl as system_command,
    find_file,
    write_file,
    get_cwd,
    set_cwd_explicit,
)

__all__ = [
    'ToolResult',
    'ToolContext',
    'UnknownToolError',
    'execute_tool_calls',
    '_execute_tool',
    'system_command',
    'find_file',
    'write_file',
    'get_cwd',
    'set_cwd_explicit',
]
