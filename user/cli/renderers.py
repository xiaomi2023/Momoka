"""
user/cli/renderers.py —— CLI 层渲染函数，供 server/servers/user/user.py 调用。

包含：
- render_todolist: 渲染待办列表（带颜色）
- render_ask_user: 渲染提问
"""

from __future__ import annotations

from rich.console import Console
from rich.text import Text


def render_todolist(console: Console, tasks: list[dict]) -> str:
    """渲染待办列表，返回渲染后的纯文本（用于日志）。

    颜色规则：
    - done: dim 灰色
    - in_progress: bright_cyan
    - pending/其他: 普通 cyan
    """
    if not tasks:
        return '(EMPTY)'

    lines: list[str | Text] = [Text('TODO List:', style='bold')]

    for i, task in enumerate(tasks, 1):
        status = task.get('status', 'pending')
        title = task.get('title', 'Unnamed task')

        if status == 'done':
            marker = '✓'
            line = Text(f'  {marker} {i}. {title}', style='dim')
        elif status == 'in_progress':
            marker = '→'
            line = Text(f'  {marker} {i}. {title}', style='bright_cyan')
        else:
            marker = '○'
            line = Text(f'  {marker} {i}. {title}', style='cyan')

        lines.append(line)
        console.print(line)

    # 返回纯文本版本（无 Rich 样式，用于日志）
    text_lines = []
    for i, task in enumerate(tasks, 1):
        status = task.get('status', 'pending')
        title = task.get('title', 'Unnamed task')
        if status == 'done':
            text_lines.append(f'  ✓ {i}. {title}')
        elif status == 'in_progress':
            text_lines.append(f'  → {i}. {title}')
        else:
            text_lines.append(f'  ○ {i}. {title}')

    return 'TODO List:\n' + '\n'.join(text_lines)


def render_ask_user(console: Console, question: str) -> None:
    """渲染提问。"""
    if question:
        console.print(question)
