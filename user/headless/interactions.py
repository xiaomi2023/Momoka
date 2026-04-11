"""
user/headless/interactions.py —— 无头模式交互适配器。

实现 AskUserCallbacks、TodoListCallbacks、SelectorCallbacks 用于工具调用。
无头模式通过 JSON Lines 格式进行通信。
"""

from __future__ import annotations

import json
import time
from typing import TYPE_CHECKING

from user.interactions import AskUserCallbacks, TodoListCallbacks
from user.selector import OptionSelector

if TYPE_CHECKING:
    from .headless import HeadlessUser


# ─────────────────────────────────────────────────────────────────────────────
# AskUser 适配器 - 用于 ask_user 工具
# ─────────────────────────────────────────────────────────────────────────────

class HeadlessAskUserAdapter:
    """无头模式 AskUser 适配器，实现 AskUserCallbacks 接口。"""

    def __init__(self, user: HeadlessUser):
        self._user = user
        self._response: str | None = None

    def make_callbacks(self) -> AskUserCallbacks:
        """构建 AskUser 的无头模式回调。"""
        return AskUserCallbacks(
            render_question=self._render_question,
            get_input=self._get_input,
        )

    def _render_question(self, question: str) -> None:
        """渲染问题到输出流。"""
        if question:
            self._user._write_json({
                'type': 'question',
                'role': 'QUESTION',
                'content': question
            })

    def _get_input(self, prompt: str) -> str:
        """从无头模式输入流获取用户输入。"""
        # 发送提示
        if prompt:
            self._user._write_json({
                'type': 'prompt',
                'role': 'QUESTION',
                'content': prompt
            })

        # 等待用户回复
        return self._wait_for_response()

    def _wait_for_response(self) -> str:
        """等待用户回复。"""
        # 从输入流读取一行
        try:
            line = self._user.get_input()
            if not line:
                return '(NULL)'

            # 解析 JSON
            try:
                msg = json.loads(line)
                if isinstance(msg, dict):
                    # 如果是 JSON 对象，尝试获取 content 字段
                    return msg.get('content', line)
                return line
            except json.JSONDecodeError:
                # 非 JSON 格式，返回原始内容
                return line
        except (EOFError, KeyboardInterrupt):
            return '(NULL)'


# ─────────────────────────────────────────────────────────────────────────────
# TodoList 适配器 - 用于 set_todolist 工具
# ─────────────────────────────────────────────────────────────────────────────

class HeadlessTodoListAdapter:
    """无头模式 TodoList 适配器，实现 TodoListCallbacks 接口。"""

    def __init__(self, user: HeadlessUser):
        self._user = user

    def make_callbacks(self) -> TodoListCallbacks:
        """构建 TodoList 的无头模式回调。"""
        return TodoListCallbacks(
            render_tasks=self._render_tasks,
        )

    def _render_tasks(self, tasks: list[dict]) -> str:
        """渲染任务列表到输出流，返回纯文本版本（用于日志）。"""
        if not tasks:
            text = '(EMPTY)'
            self._user._write_json({
                'type': 'todo',
                'role': 'TOOL',
                'content': text,
                'tasks': []
            })
            return text

        # 生成文本行
        lines = ['TODO:']
        for i, task in enumerate(tasks, 1):
            status = task.get('status', 'pending')
            title = task.get('title', 'Unnamed task')
            if status == 'done':
                lines.append(f'✓ {i}. {title}')
            elif status == 'in_progress':
                lines.append(f'→ {i}. {title}')
            else:
                lines.append(f'○ {i}. {title}')

        text = '\n'.join(lines)

        # 发送到输出流
        self._user._write_json({
            'type': 'todo',
            'role': 'TOOL',
            'content': text,
            'tasks': tasks
        })

        return text


# ─────────────────────────────────────────────────────────────────────────────
# OptionSelector 适配器 - 用于 ask_option 工具
# ─────────────────────────────────────────────────────────────────────────────

class HeadlessSelectorAdapter:
    """无头模式 OptionSelector 适配器，实现非交互式选择（编号输入模式）。"""

    def __init__(self, user: HeadlessUser):
        self._user = user

    def run_selector(self, selector: OptionSelector) -> str:
        """运行选择器，返回结果字符串。

        无头模式使用编号输入模式。
        """
        if not selector.options:
            return '<Error: No options were provided>'

        # 构建选项列表文本
        lines = [selector.question]
        for i, opt in enumerate(selector.options, 1):
            label = opt.get('label', f'Option{i}')
            desc = opt.get('description', '')
            if desc:
                lines.append(f"  {i}. {label} - {desc}")
            else:
                lines.append(f"  {i}. {label}")

        if selector.allow_multiple:
            lines.append("\n(Enter number(s), separate with commas)")
        else:
            lines.append("\n(Enter a number, or type directly for custom input)")

        display_text = '\n'.join(lines)

        # 发送到输出流
        self._user._write_json({
            'type': 'option',
            'role': 'QUESTION',
            'content': display_text,
            'question': selector.question,
            'options': selector.options,
            'allow_multiple': selector.allow_multiple
        })

        # 等待用户回复
        return self._wait_for_selection(selector)

    def _wait_for_selection(self, selector: OptionSelector) -> str:
        """等待用户选择。"""
        import re

        # 获取用户回复
        reply = self._wait_for_response()
        reply_stripped = reply.strip()

        if not reply_stripped:
            return '(No input)'

        try:
            if selector.allow_multiple:
                indices = [int(x.strip()) for x in re.split(r'[,，]', reply) if x.strip()]
                selected = []
                for idx in indices:
                    if 1 <= idx <= len(selector.options):
                        selected.append(selector.options[idx - 1].get('label', f'Option{idx}'))
                if not selected:
                    return reply_stripped
                return ', '.join(selected)
            else:
                idx = int(reply_stripped)
                if 1 <= idx <= len(selector.options):
                    return selector.options[idx - 1].get('label', f'Option{idx}')
                else:
                    return reply_stripped
        except ValueError:
            # 非数字输入视为自定义
            return reply_stripped

    def _wait_for_response(self) -> str:
        """等待用户回复。"""
        try:
            line = self._user.get_input()
            if not line:
                return '(NULL)'

            # 解析 JSON
            try:
                msg = json.loads(line)
                if isinstance(msg, dict):
                    # 如果是 JSON 对象，尝试获取 content 字段
                    return msg.get('content', line)
                return line
            except json.JSONDecodeError:
                # 非 JSON 格式，返回原始内容
                return line
        except (EOFError, KeyboardInterrupt):
            return '(NULL)'
