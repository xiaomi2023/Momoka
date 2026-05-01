"""
user/bot/qq/qq_bot.py —— QQ Bot 用户交互实现。

基于 QQ开放平台 WebSocket 网关实现 QQ 机器人接口。
继承 BotBaseUser，只实现平台特有的消息收发逻辑。
"""

from __future__ import annotations

import asyncio
import json
import os
import threading
import time
from typing import TYPE_CHECKING

import websockets
import aiohttp

from logger import log, new_log
from user.bot.base import BotBaseUser
from config import get_config

if TYPE_CHECKING:
    from host.momoka import Momoka


class QQBotUser(BotBaseUser):
    """基于 QQ开放平台 WebSocket 网关的 QQ Bot 用户交互实现。"""

    interface_type = 'qq'

    def __init__(self, app_id: str, app_secret: str, sandbox: bool = False):
        super().__init__()
        self._app_id = app_id
        self._app_secret = app_secret
        self._sandbox = sandbox

        # Access Token 管理
        self._access_token: str | None = None
        self._token_expires_at: float = 0.0

        # WebSocket 连接
        self._ws_url: str = ''
        self._session_id: str = ''
        self._seq: int = 0
        self._ws: websockets.WebSocketClientProtocol | None = None

        # 消息队列: chat_id -> asyncio.Queue of dict
        self._message_queues: dict[str, asyncio.Queue] = {}

        # 新消息事件
        self._message_event: asyncio.Event | None = None

        # 事件循环和线程
        self._event_loop: asyncio.AbstractEventLoop | None = None
        self._ws_thread: threading.Thread | None = None

        # Bot 运行标志
        self._running = False

    # ── BotBaseUser 抽象方法实现 ──────────────────────────────────────

    def _send_platform_message(self, chat_id: str, text: str) -> None:
        """向 QQ 发送文本消息。"""
        if self._event_loop and self._event_loop.is_running():
            asyncio.run_coroutine_threadsafe(
                self._send_qq_message(chat_id, text),
                self._event_loop
            ).result(timeout=30)
        else:
            loop = asyncio.new_event_loop()
            try:
                loop.run_until_complete(self._send_qq_message(chat_id, text))
            finally:
                loop.close()

    def _send_platform_file(self, chat_id: str, file_path: str, caption: str = '') -> None:
        """向 QQ 发送文件。"""
        import base64

        file_name = os.path.basename(file_path)
        with open(file_path, 'rb') as f:
            file_base64 = base64.b64encode(f.read()).decode('utf-8')

        upload_result = self._upload_file_media_sync(chat_id, file_base64, file_path, file_name)
        if not upload_result:
            raise Exception('Failed to upload file to QQ')

        file_info = upload_result.get('file_info')
        if not file_info:
            raise Exception('No file_info returned from upload')

        self._send_media_message_sync(chat_id, file_info, caption or file_name)

    def _has_platform_message(self, chat_id: str) -> bool:
        """检查指定聊天是否有新消息。"""
        queue = self._message_queues.get(chat_id)
        return queue is not None and not queue.empty()

    def _get_platform_message(self, chat_id: str) -> str | None:
        """从指定聊天的队列中获取一条消息。"""
        import asyncio as aio
        queue = self._message_queues.get(chat_id)
        if queue and not queue.empty():
            try:
                msg_data = queue.get_nowait()
                return msg_data['content']
            except aio.QueueEmpty:
                return None
        return None

    def _get_all_chat_ids(self) -> list[str]:
        """返回所有有消息队列的聊天 ID 列表。"""
        return list(self._message_queues.keys())

    def _create_interaction_adapter(self):
        """创建 QQ 交互适配器。"""
        from user.bot.qq.interactions import QQInteractionAdapter
        return QQInteractionAdapter(self)

    # ── QQ 特有逻辑 ───────────────────────────────────────────────────

    def _get_system_prompt(self) -> str:
        return "<You are communicating with user via QQ Bot>"

    def _get_api_base(self) -> str:
        if self._sandbox:
            return 'https://sandbox.api.sgroup.qq.com'
        return 'https://api.sgroup.qq.com'

    def _get_auth_header(self) -> dict:
        return {
            'Authorization': f'QQBot {self._access_token or "invalid"}',
            'Content-Type': 'application/json'
        }

    async def _get_access_token(self) -> str:
        if self._access_token and time.time() < self._token_expires_at - 60:
            return self._access_token

        url = 'https://bots.qq.com/app/getAppAccessToken'
        payload = {'appId': self._app_id, 'clientSecret': self._app_secret}

        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload) as resp:
                data = await resp.json()
                self._access_token = data['access_token']
                self._token_expires_at = time.time() + int(data.get('expires_in', 7200))
                return self._access_token

    async def _send_qq_message(self, chat_id: str, text: str) -> None:
        """通过 REST API 发送 QQ 消息。"""
        try:
            await self._get_access_token()
            headers = self._get_auth_header()

            if chat_id.startswith('group:'):
                group_openid = chat_id.split(':', 1)[1]
                url = f'{self._get_api_base()}/v2/groups/{group_openid}/messages'
                payload = {'msg_type': 0, 'content': text}
            elif chat_id.startswith('private:'):
                user_openid = chat_id.split(':', 1)[1]
                url = f'{self._get_api_base()}/v2/users/{user_openid}/messages'
                payload = {'msg_type': 0, 'content': text}
            else:
                return

            max_len = 2000
            parts = [text[i:i+max_len] for i in range(0, len(text), max_len)]

            async with aiohttp.ClientSession() as session:
                for i, part in enumerate(parts):
                    payload['content'] = part
                    async with session.post(url, headers=headers, json=payload) as resp:
                        if resp.status != 200:
                            error_text = await resp.text()
                            log(f'qq | send message part {i+1}/{len(parts)} failed: {resp.status} {error_text}')
                    if len(parts) > 1:
                        await asyncio.sleep(1)

        except Exception as e:
            log(f'qq | send message error: {e}')

    def _upload_file_media_sync(self, chat_id: str, file_base64: str, file_path: str, file_name: str = '') -> dict | None:
        """上传文件到 QQ 富媒体服务器。"""
        import asyncio

        ext = os.path.splitext(file_path)[1].lower()
        if ext in ('.png', '.jpg', '.jpeg'):
            file_type = 1
        elif ext in ('.mp4',):
            file_type = 2
        elif ext in ('.silk', '.wav', '.mp3', '.flac'):
            file_type = 3
        else:
            file_type = 4

        if chat_id.startswith('group:'):
            group_openid = chat_id.split(':', 1)[1]
            url = f'{self._get_api_base()}/v2/groups/{group_openid}/files'
        elif chat_id.startswith('private:'):
            user_openid = chat_id.split(':', 1)[1]
            url = f'{self._get_api_base()}/v2/users/{user_openid}/files'
        else:
            return None

        payload = {'file_type': file_type, 'srv_send_msg': False, 'file_data': file_base64}
        if file_type == 4 and file_name:
            payload['file_name'] = file_name

        async def upload():
            headers = self._get_auth_header()
            headers['Content-Type'] = 'application/json'
            async with aiohttp.ClientSession() as session:
                async with session.post(url, headers=headers, json=payload, timeout=aiohttp.ClientTimeout(total=60)) as resp:
                    if resp.status != 200:
                        return None
                    return await resp.json()

        if self._event_loop and self._event_loop.is_running():
            future = asyncio.run_coroutine_threadsafe(upload(), self._event_loop)
            return future.result(timeout=60)
        else:
            loop = asyncio.new_event_loop()
            try:
                return loop.run_until_complete(upload())
            finally:
                loop.close()

    def _send_media_message_sync(self, chat_id: str, file_info: str, caption: str = '') -> None:
        """发送富媒体消息。"""
        import asyncio

        if chat_id.startswith('group:'):
            group_openid = chat_id.split(':', 1)[1]
            url = f'{self._get_api_base()}/v2/groups/{group_openid}/messages'
            payload = {'content': caption, 'msg_type': 7, 'media': {'file_info': file_info}}
        elif chat_id.startswith('private:'):
            user_openid = chat_id.split(':', 1)[1]
            url = f'{self._get_api_base()}/v2/users/{user_openid}/messages'
            payload = {'msg_type': 7, 'media': {'file_info': file_info}, 'content': caption}
        else:
            return

        async def send():
            headers = self._get_auth_header()
            headers['Content-Type'] = 'application/json'
            async with aiohttp.ClientSession() as session:
                async with session.post(url, headers=headers, json=payload) as resp:
                    if resp.status != 200:
                        error_text = await resp.text()
                        log(f'qq | send_media_message failed: {resp.status} {error_text}')

        if self._event_loop and self._event_loop.is_running():
            asyncio.run_coroutine_threadsafe(send(), self._event_loop).result(timeout=30)
        else:
            loop = asyncio.new_event_loop()
            try:
                loop.run_until_complete(send())
            finally:
                loop.close()

    async def _handle_event(self, event: dict) -> None:
        """处理 WebSocket 事件。"""
        op = event.get('op')
        event_type = event.get('t')
        data = event.get('d', {})
        seq = event.get('s')

        if seq is not None:
            self._seq = seq

        if op == 0:
            if event_type == 'READY':
                self._session_id = data.get('session_id', '')
                log(f'qq | ready, session_id: {self._session_id}')

            elif event_type in ('AT_MESSAGE_CREATE', 'GROUP_AT_MESSAGE_CREATE'):
                await self._handle_group_message(data)

            elif event_type in ('C2C_MESSAGE_CREATE', 'DIRECT_MESSAGE_CREATE'):
                await self._handle_private_message(data)

        elif op == 10:
            await self._identify()

        elif op == 7:
            if self._ws:
                await self._ws.close()

        elif op == 9:
            await self._identify()

    async def _identify(self) -> None:
        """发送 Identify 鉴权消息。"""
        token = await self._get_access_token()
        intents = (1 << 25) | (1 << 30)
        payload = {
            'op': 2,
            'd': {
                'token': f'QQBot {token}',
                'intents': intents,
                'shard': [0, 1],
                'properties': {'$os': 'windows', '$browser': 'momoka', '$device': 'momoka'}
            }
        }
        await self._ws.send(json.dumps(payload))

    async def _handle_group_message(self, data: dict) -> None:
        """处理群聊消息。"""
        try:
            content = data.get('content', '').strip()
            group_openid = data.get('group_openid', '')
            author = data.get('author', {})
            attachments = data.get('attachments', [])

            chat_id = f'group:{group_openid}'

            if author.get('bot', False):
                return

            if attachments:
                for attachment in attachments:
                    await self._handle_attachment(attachment, chat_id)
                return

            if content:
                self._put_qq_message(chat_id, content)

        except Exception as e:
            log(f'qq | handle group message error: {e}')

    async def _handle_private_message(self, data: dict) -> None:
        """处理私聊消息。"""
        try:
            content = data.get('content', '').strip()
            user_openid = data.get('author', {}).get('user_openid', '')
            author = data.get('author', {})
            attachments = data.get('attachments', [])

            chat_id = f'private:{user_openid}'

            if author.get('bot', False):
                return

            if attachments:
                for attachment in attachments:
                    await self._handle_attachment(attachment, chat_id)
                return

            if content:
                self._put_qq_message(chat_id, content)

        except Exception as e:
            log(f'qq | handle private message error: {e}')

    def _put_qq_message(self, chat_id: str, content: str) -> None:
        """将 QQ 消息放入队列。"""
        if chat_id not in self._message_queues:
            self._message_queues[chat_id] = asyncio.Queue()
        self._message_queues[chat_id].put_nowait({
            'chat_id': chat_id,
            'content': content,
        })
        if self._message_event:
            self._message_event.set()

    async def _handle_attachment(self, attachment: dict, chat_id: str) -> None:
        """处理附件。"""
        try:
            filename = attachment.get('filename', 'unknown_file')
            url = attachment.get('url', '')

            if not url:
                return

            file_path = await self._download_file(url, filename)
            if file_path:
                file_content = self._read_file_content(file_path, filename)
                if file_content:
                    self._put_qq_message(
                        chat_id,
                        f"<{filename}>\n{file_content}\n</{filename}>"
                    )
                else:
                    self._put_qq_message(
                        chat_id,
                        f"<{filename}>\n[File downloaded but could not be read as text]\n</{filename}>"
                    )
        except Exception as e:
            log(f'qq | handle attachment error: {e}')

    async def _download_file(self, url: str, file_name: str) -> str | None:
        """从 URL 下载文件。"""
        try:
            import tempfile
            import uuid

            work_dir = get_config().get('work_dir', tempfile.gettempdir())
            temp_dir = os.path.join(work_dir, 'temp')
            os.makedirs(temp_dir, exist_ok=True)

            unique_name = f"{uuid.uuid4().hex[:8]}_{file_name}"
            file_path = os.path.join(temp_dir, unique_name)

            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=120)) as response:
                    if response.status != 200:
                        return None
                    with open(file_path, 'wb') as f:
                        f.write(await response.read())

            log(f'qq | file downloaded to: {file_path}')
            return file_path
        except Exception as e:
            log(f'qq | download file error: {e}')
            return None

    def _run_websocket_loop(self) -> None:
        """在独立线程中运行 WebSocket 循环。"""
        self._event_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._event_loop)

        async def connect_and_listen():
            while self._running:
                try:
                    token = await self._get_access_token()
                    ws_url = f'{self._get_api_base().replace("https://", "wss://")}/websocket/'

                    async with websockets.connect(ws_url) as ws:
                        self._ws = ws
                        log('qq | websocket connected')
                        print('Momoka connection successful')

                        while self._running:
                            try:
                                message = await asyncio.wait_for(ws.recv(), timeout=30)
                                event = json.loads(message)
                                await self._handle_event(event)
                            except asyncio.TimeoutError:
                                await self._ws.send(json.dumps({'op': 1, 'd': self._seq}))
                            except websockets.ConnectionClosed:
                                break

                except Exception as e:
                    log(f'qq | websocket error: {e}')
                    if self._running:
                        log('qq | reconnecting in 5 seconds...')
                        await asyncio.sleep(5)

        try:
            self._event_loop.run_until_complete(connect_and_listen())
        except Exception as e:
            log(f'qq | websocket loop error: {e}')

    # ── 生命周期 ───────────────────────────────────────────────────────

    def run(self) -> None:
        """启动 QQ Bot 会话循环。"""
        if self._agent is None:
            raise RuntimeError("Agent not set. Call set_agent() before run().")

        new_log()
        log('qq_bot_start')

        self._start_time = time.time()
        self.session.reset()
        self._running = True

        self._ws_thread = threading.Thread(target=self._run_websocket_loop, daemon=True)
        self._ws_thread.start()

        while not self._session_id:
            time.sleep(0.1)

        log('qq | bot ready, waiting for messages...')

        # 初始化消息事件
        self._message_event = asyncio.Event()

        # 使用基类的通用消息循环
        self._run_main_loop()

    # ── 覆盖 _on_no_message 使用事件驱动 ─────────────────────────────────

    def _on_no_message(self) -> None:
        """使用事件驱动等待，减少轮询开销。"""
        if self._message_event:
            try:
                self._message_event.wait(timeout=1.0)
                self._message_event.clear()
            except Exception:
                pass
        else:
            time.sleep(0.1)
