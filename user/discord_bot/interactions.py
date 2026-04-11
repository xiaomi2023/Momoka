"""
user/discord_bot/interactions.py —— Discord 交互适配器。

实现 SlashCommandCallbacks 接口,将纯业务逻辑层的输出适配为 Discord 格式。
同时实现 AskUserCallbacks、TodoListCallbacks、SelectorCallbacks 用于工具调用。
"""

from __future__ import annotations

import json
import time
from typing import TYPE_CHECKING

from config import get_config, get_working_config, CONFIG_FILE
from user.commands import SlashCommandCallbacks
from user.interactions import AskUserCallbacks, TodoListCallbacks
from user.selector import OptionSelector

if TYPE_CHECKING:
    from .discord_bot import DiscordBotUser


class DiscordInteractionAdapter:
    """Discord 交互适配器,实现 SlashCommandCallbacks 接口。"""

    def __init__(self, bot: DiscordBotUser):
        self._bot = bot

    def create_callbacks(self) -> SlashCommandCallbacks:
        """创建并返回 SlashCommandCallbacks 实例。"""
        return SlashCommandCallbacks(
            send_message=self._send_message,
            get_session_data=self._get_session_data,
            get_config=self._get_config,
            get_working_config=self._get_working_config,
            update_config=self._update_config,
            fetch_models=self._fetch_models,
            initialize_project=self._initialize_project,
            load_skill=self._load_skill,
            clear_context=self._clear_context,
            reset_session=self._reset_session,
        )

    def _send_message(self, text: str) -> None:
        """发送消息到 Discord。"""
        if self._bot._active_channel_id is not None:
            self._bot._send_discord_message_by_api(self._bot._active_channel_id, text)

    def _get_session_data(self) -> dict:
        """获取 session 数据。"""
        return {
            'input_tokens': self._bot.session.input_tokens,
            'output_tokens': self._bot.session.output_tokens,
            'round_count': self._bot.session.round_count,
            'start_time': self._bot._start_time,
        }

    def _get_config(self) -> dict:
        """获取静态配置。"""
        return get_config()

    def _get_working_config(self) -> dict:
        """获取运行时配置。"""
        return get_working_config()

    def _update_config(self, key: str, value: object) -> bool:
        """更新配置项。"""
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
        """从 API 拉取可用模型列表。"""
        try:
            from openai import OpenAI
            cfg = get_config()
            client = OpenAI(api_key=cfg['api_key'], base_url=cfg['base_url'])
            models = client.models.list()
            return sorted(m.id for m in models.data)
        except Exception:
            return []

    def _initialize_project(self) -> bool:
        """初始化项目,生成 AGENTS.md。"""
        if self._bot._agent is None:
            return False
        try:
            return self._bot._agent.initialize_project()
        except Exception:
            return False

    def _load_skill(self, skill_name: str) -> object:
        """加载指定 Skill。"""
        if self._bot._agent is None:
            class FailResult:
                success = False
            return FailResult()
        return self._bot._agent.load_skill(skill_name)

    def _clear_context(self) -> None:
        """清空对话上下文。"""
        if self._bot._agent is not None:
            self._bot._agent.clear_context()

    def _reset_session(self) -> None:
        """重置会话状态。"""
        self._bot.session.reset()


# ─────────────────────────────────────────────────────────────────────────────
# AskUser 适配器 - 用于 ask_user 工具
# ─────────────────────────────────────────────────────────────────────────────

class DiscordAskUserAdapter:
    """Discord AskUser 适配器，实现 AskUserCallbacks 接口。"""

    def __init__(self, bot: DiscordBotUser):
        self._bot = bot

    def make_callbacks(self) -> AskUserCallbacks:
        """构建 AskUser 的 Discord 回调。"""
        return AskUserCallbacks(
            render_question=self._render_question,
            get_input=self._get_input,
        )

    def _render_question(self, question: str) -> None:
        """渲染问题到 Discord。"""
        if self._bot._active_channel_id and question:
            self._bot._send_discord_message_by_api(
                self._bot._active_channel_id,
                f"[QUESTION]\n{question}"
            )

    def _get_input(self, prompt: str) -> str:
        """从 Discord 获取用户输入。"""
        # 等待用户回复（Discord 不需要额外的 prompt）
        return self._wait_for_response()

    def _wait_for_response(self) -> str:
        """等待用户回复。"""
        import asyncio as aio

        original_channel_id = self._bot._active_channel_id

        # 轮询等待消息
        max_wait = 600  # 最多等待 10 分钟
        waited = 0
        while waited < max_wait:
            # 检查队列中是否有新消息
            queue = self._bot._user_queues.get(original_channel_id)
            if queue and not queue.empty():
                try:
                    return queue.get_nowait()
                except aio.QueueEmpty:
                    pass
            time.sleep(0.1)
            waited += 0.1

        return '(TIMEOUT)'


# ─────────────────────────────────────────────────────────────────────────────
# TodoList 适配器 - 用于 set_todolist 工具
# ─────────────────────────────────────────────────────────────────────────────

class DiscordTodoListAdapter:
    """Discord TodoList 适配器，实现 TodoListCallbacks 接口。"""

    def __init__(self, bot: DiscordBotUser):
        self._bot = bot

    def make_callbacks(self) -> TodoListCallbacks:
        """构建 TodoList 的 Discord 回调。"""
        return TodoListCallbacks(
            render_tasks=self._render_tasks,
        )

    def _render_tasks(self, tasks: list[dict]) -> str:
        """渲染任务列表到 Discord，返回纯文本版本（用于日志）。"""
        if not tasks:
            text = '(EMPTY)'
            if self._bot._active_channel_id:
                self._bot._send_discord_message_by_api(
                    self._bot._active_channel_id,
                    text
                )
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

        # 发送到 Discord
        if self._bot._active_channel_id:
            self._bot._send_discord_message_by_api(
                self._bot._active_channel_id,
                text
            )

        return text


# ─────────────────────────────────────────────────────────────────────────────
# OptionSelector 适配器 - 用于 ask_option 工具
# ─────────────────────────────────────────────────────────────────────────────

class DiscordSelectorAdapter:
    """Discord OptionSelector 适配器，实现非交互式选择（编号输入模式）。"""

    def __init__(self, bot: DiscordBotUser):
        self._bot = bot

    def run_selector(self, selector: OptionSelector) -> str:
        """运行选择器，返回结果字符串。

        Discord 使用编号输入模式（非 TTY 模式）。
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

        # 发送到 Discord
        if self._bot._active_channel_id:
            self._bot._send_discord_message_by_api(
                self._bot._active_channel_id,
                display_text
            )

        # 等待用户回复
        return self._wait_for_selection(selector)

    def _wait_for_selection(self, selector: OptionSelector) -> str:
        """等待用户选择。"""
        import re
        import asyncio as aio

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
        import asyncio as aio

        original_channel_id = self._bot._active_channel_id

        # 轮询等待消息
        max_wait = 600  # 最多等待 10 分钟
        waited = 0
        while waited < max_wait:
            # 检查队列中是否有新消息
            queue = self._bot._user_queues.get(original_channel_id)
            if queue and not queue.empty():
                try:
                    return queue.get_nowait()
                except aio.QueueEmpty:
                    pass
            time.sleep(0.1)
            waited += 0.1

        return '(TIMEOUT)'
