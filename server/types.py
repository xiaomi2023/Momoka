"""Server 层共享类型定义。

包含所有工具执行相关的数据类和异常类定义，避免循环导入问题。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable


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

    有意不包含 work_model：
      - work_model 的历史感知逻辑（如 browse_read 去重）在 router 层完成
    
    user 为可选属性，某些工具（如 send_file）需要直接访问 user 接口。
    """
    cfg: dict
    input_func: Callable = field(default=input)
    user: Any = field(default=None)


class UnknownToolError(Exception):
    """表示工具名称在当前 Server 中无法匹配。

    由 dispatch_tool 统一捕获并转换为 ToolResult。
    """
    pass
