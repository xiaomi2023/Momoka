"""
user/lark_bot/interactions.py —— 飞书交互适配器。

实现 SlashCommandCallbacks 接口，将纯业务逻辑层的输出适配为飞书格式。
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from config import get_config, get_working_config, CONFIG_FILE
from user.commands import SlashCommandCallbacks

if TYPE_CHECKING:
    from .lark_bot import LarkBotUser


class LarkInteractionAdapter:
    """飞书交互适配器，实现 SlashCommandCallbacks 接口。"""
    
    def __init__(self, bot: LarkBotUser):
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
        )
    
    def _send_message(self, text: str) -> None:
        """发送消息到飞书。"""
        if self._bot._active_chat_id:
            self._bot._send_lark_message(self._bot._active_chat_id, text)
    
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
        """初始化项目，生成 AGENTS.md。"""
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
