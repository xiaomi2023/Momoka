"""
user/bot/interactions.py —— Bot 交互适配器公共基类。

为所有 Bot 平台（Lark、Discord、QQ）提供交互适配器的基础实现。
各平台只需实现 send_message 回调即可。
"""

from __future__ import annotations

import json
import re
import time
from typing import TYPE_CHECKING, Callable

from config import get_config, get_static_config, get_working_config, CONFIG_FILE
from user.commands import SlashCommandCallbacks
from user.interactions import AskUserCallbacks, TodoListCallbacks
from user.selector import OptionSelector

if TYPE_CHECKING:
    from user.bot.base import BotBaseUser


class BotInteractionAdapterBase:
    """Bot 交互适配器基类。

    实现 SlashCommandCallbacks 接口，各平台只需提供 _send_message 方法。
    """

    def __init__(self, bot: BotBaseUser):
        self._bot = bot

    def _send_message(self, text: str) -> None:
        """发送消息。子类需实现或通过构造函数注入。"""
        if self._bot._active_chat_id:
            self._bot._send_platform_message(self._bot._active_chat_id, text)

    def create_slash_callbacks(self) -> SlashCommandCallbacks:
        """创建并返回 SlashCommandCallbacks 实例。"""
        return SlashCommandCallbacks(
            send_message=self._send_message,
            get_session_data=self._get_session_data,
            get_config=self._get_config,
            get_static_config=self._get_static_config,
            get_working_config=self._get_working_config,
            update_config=self._update_config,
            fetch_models=self._fetch_models,
            initialize_project=self._initialize_project,
            load_skill=self._load_skill,
            clear_context=self._clear_context,
            reset_session=self._reset_session,
        )

    def _get_session_data(self) -> dict:
        return {
            'input_tokens': self._bot.session.input_tokens,
            'output_tokens': self._bot.session.output_tokens,
            'round_count': self._bot.session.round_count,
            'start_time': self._bot._start_time,
        }

    def _get_config(self) -> dict:
        return get_config()

    def _get_static_config(self) -> dict:
        return get_static_config()

    def _get_working_config(self) -> dict:
        return get_working_config()

    def _update_config(self, key: str, value: object) -> bool:
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                cfg = json.load(f)
            cfg[key] = value
            with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
                json.dump(cfg, f, ensure_ascii=False, indent=2)
            return True
        except Exception:
            return False

    def _fetch_models(self) -> list[str]:
        try:
            from model.model import fetch_available_models
            return fetch_available_models()
        except Exception:
            return []

    def _initialize_project(self) -> bool:
        if self._bot._agent is None:
            return False
        try:
            return self._bot._agent.initialize_project()
        except Exception:
            return False

    def _load_skill(self, skill_name: str) -> object:
        if self._bot._agent is None:
            class FailResult:
                success = False
            return FailResult()
        return self._bot._agent.load_skill(skill_name)

    def _clear_context(self) -> None:
        if self._bot._agent is not None:
            self._bot._agent.clear_context()

    def _reset_session(self) -> None:
        self._bot.session.reset()


class BotAskUserAdapter:
    """Bot AskUser 适配器基类。"""

    def __init__(self, bot: BotBaseUser):
        self._bot = bot

    def make_callbacks(self) -> AskUserCallbacks:
        return AskUserCallbacks(
            render_question=self._render_question,
            get_input=self._get_input,
        )

    def _render_question(self, question: str) -> None:
        if self._bot._active_chat_id and question:
            self._bot._send_platform_message(self._bot._active_chat_id, f"[QUESTION]\n{question}")

    def _get_input(self, prompt: str) -> str:
        return self._wait_for_response()

    def _wait_for_response(self) -> str:
        """等待用户回复。子类可覆盖以实现不同的队列读取逻辑。"""
        original_chat_id = self._bot._active_chat_id
        max_wait = 600
        waited = 0
        while waited < max_wait:
            msg = self._bot._get_platform_message(original_chat_id)
            if msg is not None:
                return msg
            time.sleep(0.1)
            waited += 0.1
        return '(TIMEOUT)'


class BotTodoListAdapter:
    """Bot TodoList 适配器基类。"""

    def __init__(self, bot: BotBaseUser):
        self._bot = bot

    def make_callbacks(self) -> TodoListCallbacks:
        return TodoListCallbacks(
            render_tasks=self._render_tasks,
        )

    def _render_tasks(self, tasks: list[dict]) -> str:
        if not tasks:
            text = '(EMPTY)'
            if self._bot._active_chat_id:
                self._bot._send_platform_message(self._bot._active_chat_id, text)
            return text

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
        if self._bot._active_chat_id:
            self._bot._send_platform_message(self._bot._active_chat_id, text)
        return text


class BotSelectorAdapter:
    """Bot OptionSelector 适配器基类（编号输入模式）。"""

    def __init__(self, bot: BotBaseUser):
        self._bot = bot

    def run_selector(self, selector: OptionSelector) -> str:
        if not selector.options:
            return '<Error: No options were provided>'

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
        if self._bot._active_chat_id:
            self._bot._send_platform_message(self._bot._active_chat_id, display_text)

        return self._wait_for_selection(selector)

    def _wait_for_selection(self, selector: OptionSelector) -> str:
        reply = self._wait_for_response()
        reply_stripped = reply.strip()

        if not reply_stripped:
            return '(No input)'

        try:
            if selector.allow_multiple:
                indices = [int(x.strip()) for x in re.split(r'[,，]', reply) if x.strip()]
                selected = [
                    selector.options[idx - 1].get('label', f'Option{idx}')
                    for idx in indices
                    if 1 <= idx <= len(selector.options)
                ]
                if not selected:
                    return reply_stripped
                return ', '.join(selected)
            else:
                idx = int(reply_stripped)
                if 1 <= idx <= len(selector.options):
                    return selector.options[idx - 1].get('label', f'Option{idx}')
                return reply_stripped
        except ValueError:
            return reply_stripped

    def _wait_for_response(self) -> str:
        """等待用户回复。子类可覆盖以实现不同的队列读取逻辑。"""
        original_chat_id = self._bot._active_chat_id
        max_wait = 600
        waited = 0
        while waited < max_wait:
            msg = self._bot._get_platform_message(original_chat_id)
            if msg is not None:
                return msg
            time.sleep(0.1)
            waited += 0.1
        return '(TIMEOUT)'
