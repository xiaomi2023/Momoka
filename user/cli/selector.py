"""
user/cli/selector.py —— 选项选择器的 CLI 终端适配器。

将 OptionSelector 的回调接口桥接到 Rich 终端渲染和跨平台按键监听。
使用 Rich Live 实现优雅的终端刷新，无需手动处理 ANSI 转义码。
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from typing import Callable

from rich.console import Console, Group
from rich.text import Text
from rich.live import Live


@dataclass
class SelectorCallbacks:
    """选项选择器的回调接口，由 CLI 层提供实现。"""

    get_key: Callable[[], str]
    """阻塞获取按键，返回按键字符/转义序列（如 '\\x1b[A' 表示上箭头）"""

    is_tty: Callable[[], bool]
    """检测是否为 TTY 环境"""

    start_live: Callable[[], None]
    """启动 Live 渲染"""

    update_render: Callable[[str, list[str], int, set[int], bool], None]
    """更新渲染内容 (question, labels, cursor_idx, selected_indices, allow_multiple)"""

    stop_live: Callable[[], None]
    """停止 Live 渲染"""


class CliSelectorAdapter:
    """将 OptionSelector 的回调接口桥接到 Rich 终端渲染。"""

    def __init__(self, console: Console):
        self._console = console
        self._live: Live | None = None

    def make_callbacks(self) -> SelectorCallbacks:
        """构建回调接口实例。"""
        return SelectorCallbacks(
            get_key=self._get_key,
            is_tty=self._is_tty,
            start_live=self._start_live,
            update_render=self._update_render,
            stop_live=self._stop_live,
        )

    # ── 回调实现 ───────────────────────────────────────────────────────

    def _build_renderable(
        self,
        question: str,
        labels: list[str],
        cursor_idx: int,
        selected_indices: set[int],
        allow_multiple: bool,
    ) -> Group:
        """构建 Rich 可渲染对象。"""
        items: list[Text] = []

        # 标题
        items.append(Text(question, style="bold cyan"))

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

            # 应用样式
            if is_cursor:
                items.append(Text(f"{marker}{label}", style="bold cyan"))
            elif is_selected:
                items.append(Text(f"{marker}{label}", style="green"))
            else:
                items.append(f"{marker}{label}")

        # 提示（放在最下面）
        if allow_multiple:
            items.append(Text("(↑↓ navigate, Space select, Enter confirm, ESC/q custom)", style="dim"))
        else:
            items.append(Text("(↑↓ navigate, Enter confirm, ESC/q custom)", style="dim"))

        return Group(*items)

    def _start_live(self):
        """启动 Live 渲染。"""
        if self._live is None:
            self._live = Live(
                Text(""),
                console=self._console,
                refresh_per_second=10,
                transient=True,  # 停止后自动收回
            )
            self._live.start()

    def _update_render(
        self,
        question: str,
        labels: list[str],
        cursor_idx: int,
        selected_indices: set[int],
        allow_multiple: bool,
    ):
        """更新 Rich Live 渲染内容。"""
        if self._live is not None:
            renderable = self._build_renderable(question, labels, cursor_idx, selected_indices, allow_multiple)
            self._live.update(renderable, refresh=True)

    def _stop_live(self):
        """停止 Live 渲染。"""
        if self._live is not None:
            try:
                self._live.stop()
            except Exception:
                pass
            finally:
                self._live = None

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
