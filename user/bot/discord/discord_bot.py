"""
user/bot/discord/discord_bot.py —— Discord Bot 用户交互实现。

基于 discord.py 库实现 Discord 机器人接口。
继承 BotBaseUser，只实现平台特有的消息收发逻辑。
"""

from __future__ import annotations

import asyncio
import threading
import time
from typing import TYPE_CHECKING

import discord
from discord.ext import commands

from logger import log, new_log
from user.bot.base import BotBaseUser

if TYPE_CHECKING:
    from host.momoka import Momoka


class DiscordBotUser(BotBaseUser):
    """基于 Discord Bot 的用户交互实现。"""

    interface_type = 'discord'

    def __init__(self, token: str, allowed_users: list[int] | None = None, proxy: str | None = None):
        super().__init__()
        self._token = token
        self._allowed_users = allowed_users or []
        self._proxy = proxy
        self._bot: commands.Bot | None = None
        self._user_queues: dict[int, asyncio.Queue] = {}  # channel_id -> queue
        self._event_loop: asyncio.AbstractEventLoop | None = None
        self._bot_thread: threading.Thread | None = None

    # ── BotBaseUser 抽象方法实现 ──────────────────────────────────────

    def _send_platform_message(self, chat_id: str, text: str) -> None:
        """向 Discord 发送文本消息。"""
        import aiohttp
        import asyncio as aio

        max_len = 1900
        parts = [text[i:i+max_len] for i in range(0, len(text), max_len)]

        async def send_part(part_text: str):
            proxy = self._proxy if self._proxy else None
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f'https://discord.com/api/v10/channels/{chat_id}/messages',
                    headers={
                        'Authorization': f'Bot {self._token}',
                        'Content-Type': 'application/json'
                    },
                    json={'content': part_text},
                    proxy=proxy
                ) as resp:
                    if resp.status != 200:
                        error_text = await resp.text()
                        log(f'discord | API error: {resp.status} {error_text}')

        loop = aio.new_event_loop()
        for part in parts:
            loop.run_until_complete(send_part(part))
        loop.close()

    def _send_platform_file(self, chat_id: str, file_path: str, caption: str = '') -> None:
        """向 Discord 发送文件。"""
        import aiohttp
        import asyncio as aio
        import os

        file_name = os.path.basename(file_path)

        async def send_file_async():
            proxy = self._proxy if self._proxy else None
            async with aiohttp.ClientSession() as session:
                data = aiohttp.FormData()
                if caption:
                    data.add_field('content', caption)
                with open(file_path, 'rb') as f:
                    data.add_field('files[0]', f, filename=file_name, content_type='application/octet-stream')
                    async with session.post(
                        f'https://discord.com/api/v10/channels/{chat_id}/messages',
                        headers={'Authorization': f'Bot {self._token}'},
                        data=data,
                        proxy=proxy
                    ) as resp:
                        if resp.status not in (200, 201):
                            error_text = await resp.text()
                            log(f'discord | file upload error: {resp.status} {error_text}')

        loop = aio.new_event_loop()
        loop.run_until_complete(send_file_async())
        loop.close()

    def _has_platform_message(self, chat_id: str) -> bool:
        """检查指定频道是否有新消息。"""
        import asyncio as aio
        channel_id = int(chat_id)
        queue = self._user_queues.get(channel_id)
        return queue is not None and not queue.empty()

    def _get_platform_message(self, chat_id: str) -> str | None:
        """从指定频道的队列中获取一条消息。"""
        import asyncio as aio
        channel_id = int(chat_id)
        queue = self._user_queues.get(channel_id)
        if queue and not queue.empty():
            try:
                return queue.get_nowait()
            except aio.QueueEmpty:
                return None
        return None

    def _get_all_chat_ids(self) -> list[str]:
        """返回所有有消息队列的频道 ID 列表。"""
        return [str(cid) for cid in self._user_queues.keys()]

    def _create_interaction_adapter(self):
        """创建 Discord 交互适配器。"""
        from user.bot.discord.interactions import DiscordInteractionAdapter
        return DiscordInteractionAdapter(self)

    # ── Discord 特有逻辑 ──────────────────────────────────────────────

    def _get_system_prompt(self) -> str:
        return "<You are communicating with user via Discord>"

    def _is_user_allowed(self, user_id: int) -> bool:
        if not self._allowed_users:
            return True
        return user_id in self._allowed_users

    async def _on_message(self, message: discord.Message):
        """消息接收回调。"""
        if message.author == self._bot.user:
            return
        if not self._is_user_allowed(message.author.id):
            await message.channel.send("Error: You do not have permission to use this bot.")
            return

        content = message.content.strip()
        log(f'discord | received message from {message.author}: {content}')

        if message.attachments:
            await self._handle_attachments(message)
            return

        if content:
            channel_id = message.channel.id
            if channel_id not in self._user_queues:
                self._user_queues[channel_id] = asyncio.Queue()
            await self._user_queues[channel_id].put(content)
            log(f'discord | message queued to channel {channel_id}')

    async def _handle_attachments(self, message: discord.Message):
        """处理消息附件。"""
        try:
            channel_id = message.channel.id
            for attachment in message.attachments:
                file_name = attachment.filename
                file_path = await self._download_attachment(attachment)
                if file_path:
                    file_content = self._read_file_content(file_path, file_name)
                    if file_content:
                        if channel_id not in self._user_queues:
                            self._user_queues[channel_id] = asyncio.Queue()
                        await self._user_queues[channel_id].put(
                            f"<{file_name}>\n{file_content}\n</{file_name}>"
                        )
                    else:
                        if channel_id not in self._user_queues:
                            self._user_queues[channel_id] = asyncio.Queue()
                        await self._user_queues[channel_id].put(
                            f"<{file_name}>\n[File downloaded but could not be read as text]\n</{file_name}>"
                        )
        except Exception as e:
            log(f'discord | handle attachments error: {e}')

    async def _download_attachment(self, attachment: discord.Attachment) -> str | None:
        """下载 Discord 附件。"""
        try:
            import os
            import tempfile
            import uuid
            import aiohttp

            from config import get_config
            work_dir = get_config().get('work_dir', tempfile.gettempdir())
            temp_dir = os.path.join(work_dir, 'temp')
            os.makedirs(temp_dir, exist_ok=True)

            unique_name = f"{uuid.uuid4().hex[:8]}_{attachment.filename}"
            file_path = os.path.join(temp_dir, unique_name)

            proxy = self._proxy if self._proxy else None
            async with aiohttp.ClientSession() as session:
                async with session.get(attachment.url, proxy=proxy) as resp:
                    if resp.status != 200:
                        return None
                    with open(file_path, 'wb') as f:
                        f.write(await resp.read())

            log(f'discord | attachment downloaded to: {file_path}')
            return file_path
        except Exception as e:
            log(f'discord | download attachment error: {e}')
            return None

    # ── 生命周期 ───────────────────────────────────────────────────────

    def run(self) -> None:
        """启动 Discord Bot 会话循环。"""
        if self._agent is None:
            raise RuntimeError("Agent not set. Call set_agent() before run().")

        new_log()
        log('discord_bot_start')

        self._start_time = time.time()
        self.session.reset()

        def run_bot():
            self._event_loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._event_loop)

            if self._proxy:
                import functools
                original_http_init = discord.http.HTTPClient.__init__
                proxy_url = self._proxy

                def patched_http_init(http_self, *args, **kwargs):
                    kwargs['proxy'] = proxy_url
                    original_http_init(http_self, *args, **kwargs)

                discord.http.HTTPClient.__init__ = patched_http_init

            intents = discord.Intents.default()
            intents.message_content = True
            intents.members = False

            self._bot = commands.Bot(command_prefix='!', intents=intents)

            @self._bot.event
            async def on_ready():
                log(f'discord | logged in as {self._bot.user}')
                print('Momoka connection successful')

            @self._bot.event
            async def on_message(message: discord.Message):
                await self._on_message(message)

            log('discord | bot starting')
            self._bot.run(self._token)

        self._bot_thread = threading.Thread(target=run_bot, daemon=True)
        self._bot_thread.start()

        while self._bot is None or not self._bot.is_ready():
            time.sleep(0.1)

        log('discord | bot ready, waiting for messages...')

        # 使用基类的通用消息循环
        self._run_main_loop()
