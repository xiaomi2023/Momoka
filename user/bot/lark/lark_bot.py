"""
user/bot/lark/lark_bot.py —— 飞书/Lark Bot 用户交互实现。

基于 lark-oapi SDK 实现飞书机器人接口。
使用 WebSocket 长连接模式，无需公网 IP。

继承 BotBaseUser，只实现平台特有的消息收发逻辑。
"""

from __future__ import annotations

import json
import threading
import time
from typing import TYPE_CHECKING

import lark_oapi as lark
from lark_oapi.api.im.v1 import (
    CreateMessageRequest,
    CreateMessageRequestBody,
)

from logger import log, new_log
from user.bot.base import BotBaseUser

if TYPE_CHECKING:
    from host.momoka import Momoka


class LarkBotUser(BotBaseUser):
    """基于飞书/Lark Bot 的用户交互实现。"""

    interface_type = 'lark'

    def __init__(self, app_id: str, app_secret: str):
        super().__init__()
        self._app_id = app_id
        self._app_secret = app_secret

        # 消息队列: open_chat_id -> list[message]
        self._message_queues: dict[str, list[str]] = {}
        self._queues_lock = threading.Lock()

        # 飞书 Client
        self._client: lark.Client | None = None

    # ── BotBaseUser 抽象方法实现 ──────────────────────────────────────

    def _send_platform_message(self, chat_id: str, text: str) -> None:
        """向飞书发送文本消息。"""
        try:
            client = self._get_client()
            msg_content = json.dumps({"text": text})
            request = (
                CreateMessageRequest.builder()
                .receive_id_type('chat_id')
                .request_body(
                    CreateMessageRequestBody.builder()
                    .receive_id(chat_id)
                    .msg_type('text')
                    .content(msg_content)
                    .build()
                )
                .build()
            )
            response = client.im.v1.message.create(request)
            if not response.success():
                log(f'lark | send message failed: {response.code} {response.msg}')
            else:
                log(f'lark | message sent to {chat_id}')
        except Exception as e:
            log(f'lark | send error: {e}')

    def _send_platform_file(self, chat_id: str, file_path: str, caption: str = '') -> None:
        """向飞书发送文件。"""
        import os

        try:
            client = self._get_client()
            file_name = os.path.basename(file_path)
            log(f'lark | uploading file: {file_name}')

            file_ext = os.path.splitext(file_name)[1].lower()
            image_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp'}
            is_image = file_ext in image_extensions

            if is_image:
                from lark_oapi.api.im.v1 import (
                    CreateImageRequest, CreateImageRequestBody,
                )
                with open(file_path, 'rb') as img_file:
                    upload_request = (
                        CreateImageRequest.builder()
                        .request_body(
                            CreateImageRequestBody.builder()
                            .image_type('message')
                            .image(img_file)
                            .build()
                        )
                        .build()
                    )
                    upload_response = client.im.v1.image.create(upload_request)

                if not upload_response.success():
                    log(f'lark | image upload failed: {upload_response.code} {upload_response.msg}')
                    return

                msg_content = json.dumps({"image_key": upload_response.data.image_key})
                msg_type = 'image'
            else:
                from lark_oapi.api.im.v1 import (
                    CreateFileRequest, CreateFileRequestBody,
                )
                with open(file_path, 'rb') as file_stream:
                    upload_request = (
                        CreateFileRequest.builder()
                        .request_body(
                            CreateFileRequestBody.builder()
                            .file_type('stream')
                            .file_name(file_name)
                            .file(file_stream)
                            .build()
                        )
                        .build()
                    )
                    upload_response = client.im.v1.file.create(upload_request)

                if not upload_response.success():
                    log(f'lark | file upload failed: {upload_response.code} {upload_response.msg}')
                    return

                msg_content = json.dumps({"file_key": upload_response.data.file_key})
                msg_type = 'file'

            from lark_oapi.api.im.v1 import (
                CreateMessageRequest as LarkCreateMessageRequest,
                CreateMessageRequestBody as LarkCreateMessageRequestBody,
            )
            message_request = (
                LarkCreateMessageRequest.builder()
                .receive_id_type('chat_id')
                .request_body(
                    LarkCreateMessageRequestBody.builder()
                    .receive_id(chat_id)
                    .msg_type(msg_type)
                    .content(msg_content)
                    .build()
                )
                .build()
            )
            message_response = client.im.v1.message.create(message_request)
            if not message_response.success():
                log(f'lark | send file message failed: {message_response.code} {message_response.msg}')

            log(f'lark | file sent: {file_name}')
            if caption:
                self._send_platform_message(chat_id, caption)

        except Exception as e:
            log(f'lark | send file error: {e}')
            import traceback
            log(f'lark | traceback: {traceback.format_exc()}')

    def _has_platform_message(self, chat_id: str) -> bool:
        """检查指定聊天是否有新消息。"""
        with self._queues_lock:
            return chat_id in self._message_queues and len(self._message_queues[chat_id]) > 0

    def _get_platform_message(self, chat_id: str) -> str | None:
        """从指定聊天的队列中获取一条消息。"""
        with self._queues_lock:
            queue = self._message_queues.get(chat_id, [])
            if queue:
                return queue.pop(0)
            return None

    def _get_all_chat_ids(self) -> list[str]:
        """返回所有有消息队列的聊天 ID 列表。"""
        with self._queues_lock:
            return list(self._message_queues.keys())

    def _create_interaction_adapter(self):
        """创建飞书交互适配器。"""
        from user.bot.lark.interactions import LarkInteractionAdapter
        return LarkInteractionAdapter(self)

    # ── 飞书特有逻辑 ───────────────────────────────────────────────────

    def _get_system_prompt(self) -> str:
        return "<You are communicating with user via Lark>"

    def _get_client(self) -> lark.Client:
        if self._client is None:
            self._client = (
                lark.Client.builder()
                .app_id(self._app_id)
                .app_secret(self._app_secret)
                .build()
            )
        return self._client

    def _handle_message_event(self, data: lark.P2ImMessageReceiveV1) -> None:
        """处理接收到的飞书消息事件。"""
        try:
            event = data.event
            message = event.message
            msg_type = message.message_type
            chat_id = message.chat_id

            if msg_type == 'text':
                content = message.content
                try:
                    content_obj = json.loads(content)
                    text = content_obj.get('text', '')
                except json.JSONDecodeError:
                    text = content

                if text.startswith('@_user_'):
                    parts = text.split(' ', 1)
                    if len(parts) > 1:
                        text = parts[1].strip()

                log(f'lark | receive from {chat_id}: {text}')
                self._put_message_internal(chat_id, text)

            elif msg_type == 'file':
                self._handle_file_message(message, chat_id)
            else:
                log(f'lark | unsupported message type: {msg_type}')
        except Exception as e:
            log(f'lark | parse message error: {e}')

    def _put_message_internal(self, chat_id: str, message: str) -> None:
        """将消息放入队列。"""
        with self._queues_lock:
            if chat_id not in self._message_queues:
                self._message_queues[chat_id] = []
            self._message_queues[chat_id].append(message)

    def _handle_file_message(self, message, chat_id: str) -> None:
        """处理接收到的文件消息。"""
        try:
            content = message.content
            message_id = message.message_id
            try:
                content_obj = json.loads(content)
                file_key = content_obj.get('file_key', '')
                file_name = content_obj.get('file_name', 'unknown_file')
            except json.JSONDecodeError:
                return

            if not file_key:
                return

            log(f'lark | receive file from {chat_id}: {file_name}')

            file_path = self._download_lark_file(message_id, file_key, file_name)
            if file_path:
                file_content = self._read_file_content(file_path, file_name)
                if file_content:
                    self._put_message_internal(
                        chat_id,
                        f"<{file_name}>\n{file_content}\n</{file_name}>"
                    )
                else:
                    self._put_message_internal(
                        chat_id,
                        f"<{file_name}>\n[File downloaded to: {file_path} but could not be read as text]\n</{file_name}>"
                    )
            else:
                log(f'lark | failed to download file: {file_name}')
                self._send_platform_message(chat_id, f"Failed to receive file: {file_name}")
        except Exception as e:
            log(f'lark | handle file message error: {e}')
            import traceback
            log(f'lark | traceback: {traceback.format_exc()}')

    def _download_lark_file(self, message_id: str, file_key: str, file_name: str) -> str | None:
        """从飞书消息中下载资源文件。"""
        try:
            import os
            import tempfile
            import uuid
            import requests

            token = self._get_tenant_access_token()
            if not token:
                return None

            url = f'https://open.feishu.cn/open-apis/im/v1/messages/{message_id}/resources/{file_key}?type=file'
            headers = {'Authorization': f'Bearer {token}'}
            response = requests.get(url, headers=headers, timeout=60)

            if response.status_code != 200:
                return None

            work_dir = get_config().get('work_dir', tempfile.gettempdir())
            temp_dir = os.path.join(work_dir, 'temp')
            os.makedirs(temp_dir, exist_ok=True)

            unique_name = f"{uuid.uuid4().hex[:8]}_{file_name}"
            file_path = os.path.join(temp_dir, unique_name)

            with open(file_path, 'wb') as f:
                f.write(response.content)

            log(f'lark | file downloaded to: {file_path}')
            return file_path

        except Exception as e:
            log(f'lark | download file error: {e}')
            return None

    def _get_tenant_access_token(self) -> str | None:
        """获取飞书 tenant_access_token。"""
        try:
            import requests
            url = 'https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal'
            payload = {
                'app_id': self._app_id,
                'app_secret': self._app_secret
            }
            response = requests.post(url, json=payload, timeout=30)
            result = response.json()
            if result.get('code') != 0:
                return None
            return result.get('tenant_access_token')
        except Exception as e:
            log(f'lark | get tenant_access_token error: {e}')
            return None

    # ── 生命周期 ───────────────────────────────────────────────────────

    def run(self) -> None:
        """启动飞书 Bot 会话循环。"""
        if self._agent is None:
            raise RuntimeError("Agent not set. Call set_agent() before run().")

        new_log()
        log('lark_bot_start')

        self._start_time = time.time()
        self.session.reset()

        def on_message(data: lark.P2ImMessageReceiveV1) -> None:
            self._handle_message_event(data)

        event_handler = (
            lark.EventDispatcherHandler.builder("", "")
            .register_p2_im_message_receive_v1(on_message)
            .build()
        )

        ws_client = lark.ws.Client(
            app_id=self._app_id,
            app_secret=self._app_secret,
            event_handler=event_handler,
            log_level=lark.LogLevel.DEBUG,
        )

        def run_ws():
            log('lark | WebSocket connecting...')
            ws_client.start()

        ws_thread = threading.Thread(target=run_ws, daemon=True)
        ws_thread.start()
        time.sleep(2)
        print('Momoka connection successful')

        # 使用基类的通用消息循环
        self._run_main_loop()
