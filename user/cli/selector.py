"""
user/cli/selector.py —— 选项选择器的 CLI 终端适配器。

将 OptionSelector 的回调接口桥接到 Rich 终端渲染和跨平台按键监听。
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from typing import Callable

from rich.console import Console
from rich.text import Text


@dataclass
class SelectorCallbacks:
    """选项选择器的回调接口，由 CLI 层提供实现。"""

    render: Callable[[str, list[str], int, set[int], bool], None]
    """渲染函数 (question, labels, cursor_idx, selected_indices, allow_multiple)"""

    get_key: Callable[[], str]
    """阻塞获取按键，返回按键字符/转义序列（如 '\\x1b[A' 表示上箭头）"""

    is_tty: Callable[[], bool]
    """检测是否为 TTY 环境"""

    clear_lines: Callable[[int], None]
    """清除指定行数的输出"""


class CliSelectorAdapter:
    """将 OptionSelector 的回调接口桥接到 Rich 终端渲染。"""

    def __init__(self, console: Console):
        self._console = console

    def make_callbacks(self) -> SelectorCallbacks:
        """构建回调接口实例。"""
        return SelectorCallbacks(
            render=self._render,
            get_key=self._get_key,
            is_tty=self._is_tty,
            clear_lines=self._clear_lines,
        )

    # ── 回调实现 ───────────────────────────────────────────────────────

    def _render(
        self,
        question: str,
        labels: list[str],
        cursor_idx: int,
        selected_indices: set[int],
        allow_multiple: bool,
    ):
        """使用 Rich 渲染选项列表。"""
        lines: list[str | Text] = []

        # 标题
        lines.append(Text(question, style='bold cyan'))

        # 提示
        if allow_multiple:
            lines.append(Text('(↑↓ navigate, Space select, Enter confirm, ESC/q custom)', style='dim'))
        else:
            lines.append(Text('(↑↓ navigate, Enter confirm, ESC/q custom)', style='dim'))

        # 选项
        for i, label in enumerate(labels):
            is_cursor = i == cursor_idx
            is_selected = i in selected_indices

            # 构建标记
            if allow_multiple:
                marker = '[✓] ' if is_selected else '[ ] '
            else:
                marker = ''

            if is_cursor:
                marker = '▶ ' + marker
            else:
                marker = '  ' + marker

            if is_cursor:
                lines.append(Text(marker + label, style='bold cyan'))
            elif is_selected:
                lines.append(Text(marker + label, style='green'))
            else:
                lines.append(marker + label)

        # 空行
        lines.append('')

        # 清屏并重绘
        self._clear_lines(len(lines))
        for line in lines:
            if isinstance(line, Text):
                self._console.print(line)
            else:
                self._console.print(line)

    def _get_key(self) -> str:
        """跨平台阻塞获取按键。"""
        if sys.platform == 'win32':
            return self._get_key_windows()
        else:
            return self._get_key_unix()

    def _get_key_windows(self) -> str:
        import msvcrt

        key = msvcrt.getch()

        # 特殊键前缀
        if key in (b'\x00', b'\xe0'):
            key2 = msvcrt.getch()
            if key2 == b'H':
                return '\x1b[A'  # Up
            elif key2 == b'P':
                return '\x1b[B'  # Down
            return ''

        # 普通键
        if key == b'\r':
            return '\r'
        elif key == b' ':
            return ' '
        elif key == b'\x1b':
            return '\x1b'
        elif key in (b'q', b'Q'):
            return 'q'

        return key.decode('utf-8', errors='replace')

    def _get_key_unix(self) -> str:
        import termios
        import tty

        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)

        try:
            tty.setraw(fd)
            ch = sys.stdin.read(1)

            if ch == '\x1b':  # ESC 序列
                ch2 = sys.stdin.read(1)
                if ch2 == '[':
                    ch3 = sys.stdin.read(1)
                    if ch3 == 'A':
                        return '\x1b[A'  # Up
                    elif ch3 == 'B':
                        return '\x1b[B'  # Down
                return '\x1b'  # 裸 ESC
            elif ch in ('\r', '\n'):
                return '\r'
            elif ch == ' ':
                return ' '
            elif ch in ('q', 'Q'):
                return 'q'
            else:
                return ch
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)

    def _is_tty(self) -> bool:
        return sys.stdout.isatty() and sys.stdin.isatty()

    def _clear_lines(self, count: int):
        """清除指定行数的输出。"""
        if count <= 0:
            return
        # 上移并清空
        sys.stdout.write(f'\x1b[{count}A\r')
        for _ in range(count):
            sys.stdout.write('\x1b[K\n')
        sys.stdout.write(f'\x1b[{count}A\r')
        sys.stdout.flush()
