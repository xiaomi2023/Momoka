"""Server 层共享类型定义。

包含所有工具执行相关的数据类和异常类定义，避免循环导入问题。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass
class ToolResult:
    """工具执行结果。

    text:       返回给 model 的文字内容
    success:    工具是否执行成功（默认 True）
    log_msg:    需要输出给用户的日志；None 表示不 log
                str                        → 单条，role 由 log_role 决定
                list[dict]                 → 多条，每项为 {msg, role, panel?, panel_title?}
    log_role:   单条 log 时的 role，默认 'TOOL'
    panel:      可选。若不为空，CLI 层用 Rich Panel 包裹 log_msg。
                仅对单条 log_msg 生效。
    panel_title: Panel 标题，为 None 时使用 log_role。
    """
    text: str
    success: bool = True
    log_msg: str | list[dict] | None = None
    log_role: str = 'TOOL'
    panel: bool = False
    panel_title: str | None = None


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
