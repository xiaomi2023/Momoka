"""
host/conversation_manager.py —— 对话历史管理。

负责加载预设对话、修复孤儿 tool_calls 消息等历史管理操作。
"""

from __future__ import annotations

import json
import os

from logger import log
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from model.model import Model


class ConversationManager:
    """对话历史管理器，负责预设对话加载和历史修复。"""

    def __init__(self, model: Model) -> None:
        self._model = model

    def load_preset_conversations(self) -> None:
        """从文件加载预设对话并插入到模型历史中。"""
        preset_file = os.path.join(
            os.path.dirname(__file__),
            'prompt',
            'preset_convs.json',
        )
        try:
            with open(preset_file, 'r', encoding='utf-8') as f:
                preset_convs = json.load(f)
            self._model._ctx.insert_preset_conversations(preset_convs)
        except (FileNotFoundError, json.JSONDecodeError) as e:
            log(f'conversation_manager.load_preset_conversations | Failed to load preset conversations: {e}')

    def repair_history(self) -> int:
        """修复历史中孤立的 tool_calls 消息。

        Returns:
            修复的消息数量
        """
        return self._model.repair_history()
