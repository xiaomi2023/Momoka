"""
user/bot/lark/interactions.py —— 飞书交互适配器。

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
    from .lark_bot import LarkBotUser


class LarkInteractionAdapter(BotInteractionAdapterBase):
    """飞书交互适配器。"""

    def __init__(self, bot: LarkBotUser):
        super().__init__(bot)


class LarkAskUserAdapter(BotAskUserAdapter):
    """飞书 AskUser 适配器。"""

    def __init__(self, bot: LarkBotUser):
        super().__init__(bot)


class LarkTodoListAdapter(BotTodoListAdapter):
    """飞书 TodoList 适配器。"""

    def __init__(self, bot: LarkBotUser):
        super().__init__(bot)


class LarkSelectorAdapter(BotSelectorAdapter):
    """飞书选择器适配器。"""

    def __init__(self, bot: LarkBotUser):
        super().__init__(bot)
