"""Server package — Tool execution and browser automation."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable


# ── 数据类定义 ─────────────────────────────────────────────────────────────
# 注意：这些类定义在 __init__.py 中是为了避免循环导入问题

@dataclass
class ToolResult:
    """工具执行结果。

    text:          返回给 model 的文字内容
    file_contents: 本次读取的文件内容，格式 {file_key: content}
    is_finish:     True 表示调用了 finish()，本轮终止
    log_msg:       需要输出给用户的日志；None 表示不 log
                   str                   → 单条，role 由 log_role 决定
                   list[tuple[str,str]]  → 多条，每项为 (msg, role)
    log_role:      单条 log 时的 role，默认 'TOOL'
    """
    text: str
    file_contents: dict[str, str] = field(default_factory=dict)
    is_finish: bool = False
    log_msg: str | list[tuple[str, str]] | None = None
    log_role: str = 'TOOL'


@dataclass
class ToolContext:
    """工具执行所需的只读上下文。

    有意不包含 user / work_model：
      - user_log  由 router 统一处理，handler 只填写 ToolResult.log_msg
      - work_model 的历史感知逻辑（如 browse_read 去重）也在 router 层完成
    """
    cfg: dict
    input_func: Callable = field(default=input)


# ── 延迟导入函数 ────────────────────────────────────────────────────────────
# 在类定义之后导入，避免循环导入

from server.router import execute_tool_calls, _execute_tool
from server.servers.system.system import _system_command_impl as system_command, find_file, edit_file, get_cwd, set_cwd_explicit

__all__ = [
    'execute_tool_calls', '_execute_tool', 'ToolResult', 'ToolContext',
    'system_command', 'find_file', 'edit_file', 'get_cwd', 'set_cwd_explicit',
]
