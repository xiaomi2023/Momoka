"""
user/interactions.py —— 用户交互功能的纯业务逻辑抽象层。

包含：
- AskUser: 提问并获取用户回复
- TodoList: 展示待办任务列表
- OptionSelector: 选项选择（已有，从 selector.py 迁移过来统一管理）

所有类都是纯业务逻辑，不依赖任何 UI 框架。
通过回调接口（Callbacks）注入渲染和输入能力。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable


# ─────────────────────────────────────────────────────────────────────
# AskUser - 提问交互
# ─────────────────────────────────────────────────────────────────────

@dataclass
class AskUserCallbacks:
    """提问交互的回调接口，由具体 UI 层实现。"""

    render_question: Callable[[str], None]
    """渲染问题到界面"""

    get_input: Callable[[str], str]
    """获取用户输入 (prompt) -> str"""


class AskUser:
    """提问交互的纯业务逻辑。

    职责：
    - 管理问题和回复的生命周期
    - 通过回调接口进行渲染和输入
    """

    def __init__(self, question: str):
        self.question = question

    def run(self, callbacks: AskUserCallbacks) -> str:
        """运行提问交互，返回用户回复。

        Args:
            callbacks: UI 层提供的回调接口

        Returns:
            用户的回复文本，如果为空返回 '(NULL)'
        """
        if not self.question:
            return '(NULL)'

        callbacks.render_question(self.question)
        reply = callbacks.get_input('')

        return reply if reply else '(NULL)'


# ─────────────────────────────────────────────────────────────────────
# TodoList - 待办列表展示
# ─────────────────────────────────────────────────────────────────────

@dataclass
class TodoListCallbacks:
    """待办列表展示的回调接口，由具体 UI 层实现。"""

    render_tasks: Callable[[list[dict]], str]
    """渲染任务列表到界面，返回纯文本版本（用于日志）"""


class TodoList:
    """待办列表展示的纯业务逻辑。

    职责：
    - 管理任务数据
    - 通过回调接口进行渲染
    - 提供日志格式的纯文本
    """

    def __init__(self, tasks: list[dict]):
        """初始化待办列表。

        Args:
            tasks: 任务列表，每个任务包含 title 和 status 字段
        """
        self.tasks = tasks or []

    def run(self, callbacks: TodoListCallbacks) -> str:
        """运行待办列表展示，返回纯文本版本。

        Args:
            callbacks: UI 层提供的回调接口

        Returns:
            纯文本版本的任务列表（用于日志）
        """
        if not self.tasks:
            callbacks.render_tasks([])
            return '(EMPTY)'

        return callbacks.render_tasks(self.tasks)
