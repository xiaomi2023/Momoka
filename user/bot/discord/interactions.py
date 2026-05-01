"""
user/bot/discord/interactions.py —— Discord 交互适配器。

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
    from .discord_bot import DiscordBotUser


class DiscordInteractionAdapter(BotInteractionAdapterBase):
    """Discord 交互适配器。"""

    def __init__(self, bot: DiscordBotUser):
        super().__init__(bot)


class DiscordAskUserAdapter(BotAskUserAdapter):
    """Discord AskUser 适配器。"""

    def __init__(self, bot: DiscordBotUser):
        super().__init__(bot)


class DiscordTodoListAdapter(BotTodoListAdapter):
    """Discord TodoList 适配器。"""

    def __init__(self, bot: DiscordBotUser):
        super().__init__(bot)


class DiscordSelectorAdapter(BotSelectorAdapter):
    """Discord 选择器适配器。"""

    def __init__(self, bot: DiscordBotUser):
        super().__init__(bot)
