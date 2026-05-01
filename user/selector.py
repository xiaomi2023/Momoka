"""
user/selector.py —— 交互式选项选择器（纯业务逻辑）。

只负责选项状态管理、导航逻辑计算、结果格式化。
所有终端渲染和按键监听通过回调接口注入。

与 CLI 平台的具体回调实现（SelectorCallbacks）解耦：
- SelectorCallbacks 定义在 user/cli/selector.py（CLI 特有）
- OptionSelector.run() 通过 TYPE_CHECKING 引用，避免运行时 import 依赖
- 非 CLI 平台（Bot/Headless）不使用 SelectorCallbacks，直接调用 _fallback_numbered
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from user.cli.selector import SelectorCallbacks


class OptionSelector:
    """交互式选项选择器，纯业务逻辑。

    支持：
    - 单选/多选模式
    - 箭头键导航（↑↓）
    - 空格键选中/取消（仅多选）
    - Enter 确认
    - ESC/q 进入自定义输入模式
    - 降级为编号输入（非 TTY 环境 / Bot 平台）
    """

    def __init__(
        self,
        options: list[dict],
        question: str,
        allow_multiple: bool = False,
    ):
        self.options = options
        self.question = question
        self.allow_multiple = allow_multiple
        self.cursor_idx = 0
        self.selected_indices: set[int] = set()

    def run(self, callbacks: 'SelectorCallbacks' = None, input_func=None) -> str:
        """运行交互式选择，返回结果字符串。

        Args:
            callbacks: CLI 层提供的回调接口（CLI 模式必须），非 CLI 模式传 None
            input_func: 用于自定义输入模式（可选）

        Bot/Headless 等非 CLI 平台应直接调用 fallback_numbered()。
        """
        if not self.options:
            return '<Error: No options were provided>'

        # CLI 交互模式需要 callbacks
        if callbacks is not None:
            # 检测是否支持 TTY
            if not callbacks.is_tty():
                return self._fallback_numbered(input_func)

            # 尝试交互式选择
            try:
                return self._interactive(callbacks, input_func)
            except Exception:
                return self._fallback_numbered(input_func)

        # 没有 callbacks → 降级为编号输入
        return self._fallback_numbered(input_func)

    def fallback_numbered(self, input_func=None) -> str:
        """公有方法，供 Bot/Headless 平台直接调用编号输入模式。

        Args:
            input_func: 输入函数，默认为内置 input

        Returns:
            用户选择结果字符串
        """
        return self._fallback_numbered(input_func)

    # ── 交互式选择 ─────────────────────────────────────────────────────

    def _interactive(self, callbacks: 'SelectorCallbacks', input_func=None):
        """交互式选择主循环。"""
        labels = self._get_labels()

        # 启动 Live 渲染
        callbacks.start_live()

        # 首次渲染
        callbacks.update_render(self.question, labels, self.cursor_idx, self.selected_indices, self.allow_multiple)

        try:
            while True:
                key = callbacks.get_key()

                if key == '\x1b[A':  # Up
                    self.cursor_idx = (self.cursor_idx - 1) % len(self.options)
                    callbacks.update_render(self.question, labels, self.cursor_idx, self.selected_indices, self.allow_multiple)
                elif key == '\x1b[B':  # Down
                    self.cursor_idx = (self.cursor_idx + 1) % len(self.options)
                    callbacks.update_render(self.question, labels, self.cursor_idx, self.selected_indices, self.allow_multiple)
                elif key == '\r':  # Enter
                    return self._confirm_selection(callbacks)
                elif key == ' ' and self.allow_multiple:  # Space（仅多选）
                    self._toggle_selection()
                    callbacks.update_render(self.question, labels, self.cursor_idx, self.selected_indices, self.allow_multiple)
                elif key == '\x1b' or key in ('q', 'Q'):  # ESC/q → 自定义输入
                    return self._custom_input(input_func, callbacks)
        finally:
            # 确保停止 Live 渲染
            callbacks.stop_live()

    # ── 降级：编号输入 ─────────────────────────────────────────────────

    def _fallback_numbered(self, input_func=None) -> str:
        """传统编号输入模式，始终可用。"""
        lines = [self.question]
        for i, opt in enumerate(self.options, 1):
            label = opt.get('label', f'Option{i}')
            desc = opt.get('description', '')
            if desc:
                lines.append(f"  {i}. {label} - {desc}")
            else:
                lines.append(f"  {i}. {label}")

        if self.allow_multiple:
            lines.append("\n(Enter number(s), separate with commas)")
        else:
            lines.append("\n(Enter a number, or type directly for custom input)")

        display_text = '\n'.join(lines)
        print(display_text)

        if input_func is None:
            input_func = input

        reply = input_func('-> ')
        reply_stripped = reply.strip()

        if not reply_stripped:
            return self._format_result([], is_custom=False, custom_text='(No input)')

        try:
            if self.allow_multiple:
                indices = [int(x.strip()) for x in re.split(r'[,，]', reply) if x.strip()]
                selected = []
                for idx in indices:
                    if 1 <= idx <= len(self.options):
                        selected.append(self.options[idx - 1].get('label', f'Option{idx}'))
                if not selected:
                    return self._format_result([], is_custom=True, custom_text=reply_stripped)
                return self._format_result(selected, is_custom=False)
            else:
                idx = int(reply_stripped)
                if 1 <= idx <= len(self.options):
                    label = self.options[idx - 1].get('label', f'Option{idx}')
                    return self._format_result([label], is_custom=False)
                else:
                    return self._format_result([], is_custom=True, custom_text=reply_stripped)
        except ValueError:
            # 非数字输入视为自定义
            return self._format_result([], is_custom=True, custom_text=reply_stripped)

    # ── 辅助方法 ───────────────────────────────────────────────────────

    def _get_labels(self) -> list[str]:
        """获取所有选项的标签列表。"""
        return [opt.get('label', f'Option{i + 1}') for i, opt in enumerate(self.options)]

    def _toggle_selection(self):
        """切换当前光标选项的选中状态（仅多选模式）。"""
        if self.cursor_idx in self.selected_indices:
            self.selected_indices.remove(self.cursor_idx)
        else:
            self.selected_indices.add(self.cursor_idx)

    def _confirm_selection(self, callbacks: 'SelectorCallbacks') -> str:
        """确认当前选择并返回结果。"""
        if self.allow_multiple:
            if not self.selected_indices:
                result = self._format_result([], is_custom=False, custom_text='(No selection)')
            else:
                selected = [
                    self.options[i].get('label', f'Option{i+1}')
                    for i in sorted(self.selected_indices)
                ]
                result = self._format_result(selected, is_custom=False)
        else:
            label = self.options[self.cursor_idx].get('label', f'Option{self.cursor_idx+1}')
            result = self._format_result([label], is_custom=False)

        # 停止 Live 渲染，transient 模式会自动保留最终渲染内容
        callbacks.stop_live()

        return result

    def _custom_input(self, input_func=None, callbacks=None) -> str:
        """进入自定义输入模式。"""
        # 先停止 Live 渲染，再获取用户输入
        if callbacks is not None:
            callbacks.stop_live()

        if input_func is None:
            input_func = input

        reply = input_func('-> ')
        reply_stripped = reply.strip()
        if reply_stripped:
            return self._format_result([], is_custom=True, custom_text=reply_stripped)
        else:
            return self._format_result([], is_custom=True, custom_text='(No input)')

    # ── 结果格式化 ─────────────────────────────────────────────────────

    def _format_result(
        self,
        selected: list[str],
        is_custom: bool,
        custom_text: str = '',
    ) -> str:
        """格式化选择结果为 ToolResult.text 格式。"""
        if is_custom:
            return f'{custom_text}'
        if not selected:
            return '(NULL)'
        return f'{", ".join(selected)}'
