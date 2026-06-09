"""
user/cli/interactions.py —— CLI 层的用户交互适配器。

将 user/interactions.py 的回调接口桥接到 Rich 终端渲染。
"""

from __future__ import annotations

from rich.console import Console, Group
from rich.panel import Panel
from rich.text import Text

from user.interactions import AskUserCallbacks, TodoListCallbacks


class CliInteractionAdapter:
    """将用户交互的回调接口桥接到 Rich 终端渲染。"""

    def __init__(self, console: Console):
        self._console = console

    def make_ask_user_callbacks(self) -> AskUserCallbacks:
        """构建 AskUser 的 CLI 回调。"""
        return AskUserCallbacks(
            render_question=self._render_question,
            get_input=self._get_input,
        )

    def make_todolist_callbacks(self) -> TodoListCallbacks:
        """构建 TodoList 的 CLI 回调。"""
        return TodoListCallbacks(
            render_tasks=self._render_tasks,
        )

    # ── 回调实现 ───────────────────────────────────────────────────────

    def _render_question(self, question: str):
        """渲染问题到终端。"""
        if question:
            self._console.print(Text(question, style='plum1'))

    def _get_input(self, prompt: str) -> str:
        """从终端获取用户输入。"""
        try:
            return input('-> ')
        except (EOFError, KeyboardInterrupt):
            return ''

    def _render_tasks(self, tasks: list[dict]) -> str:
        """渲染待办列表到终端，返回纯文本版本（仅用于日志）。

        颜色规则：
        - done: dim 灰色
        - in_progress: bright_cyan
        - pending/其他: 普通 cyan
        """
        if not tasks:
            self._console.print(Panel('(EMPTY)', width=self._console.width))
            return '(EMPTY)'

        rich_lines: list[Text] = []
        text_lines: list[str] = []

        for i, task in enumerate(tasks, 1):
            status = task.get('status', 'pending')
            title = task.get('title', 'Unnamed task')

            if status == 'done':
                marker = '✓'
                style = 'dim'
            elif status == 'in_progress':
                marker = '→'
                style = 'bright_cyan'
            else:
                marker = '○'
                style = 'cyan'

            rich_lines.append(Text(f' {marker} {i}. {title}', style=style))
            text_lines.append(f' {marker} {i}. {title}')

        panel = Panel(
            Group(*rich_lines),
            width=self._console.width,
            title='TODO',
            title_align='left',
            border_style='dim',
        )
        self._console.print(panel)

        return 'TODO List:\n' + '\n'.join(text_lines)
