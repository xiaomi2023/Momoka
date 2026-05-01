"""
user/bot/qq/interactions.py —— QQ Bot 交互适配器。

继承 Bot 基类适配器，只需注入 bot 实例，全部逻辑由基类完成。
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from user.bot.interactions import (
    BotInteractionAdapterBase,
    BotAskUserAdapter,
    BotTodoListAdapter,
    BotSelectorAdapter,
)

if TYPE_CHECKING:
    from .qq_bot import QQBotUser


class QQInteractionAdapter(BotInteractionAdapterBase):
    """QQ 交互适配器。"""

    def __init__(self, bot: QQBotUser):
        super().__init__(bot)


class QQAskUserAdapter(BotAskUserAdapter):
    """QQ AskUser 适配器。"""

    def __init__(self, bot: QQBotUser):
        super().__init__(bot)


class QQTodolistAdapter(BotTodoListAdapter):
    """QQ TodoList 适配器。"""

    def __init__(self, bot: QQBotUser):
        super().__init__(bot)


class QQSelectorAdapter(BotSelectorAdapter):
    """QQ 选择器适配器。"""

    def __init__(self, bot: QQBotUser):
        super().__init__(bot)
