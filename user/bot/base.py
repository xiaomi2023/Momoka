"""
user/bot/base.py —— Bot 平台公共基类。

为所有 Bot 平台（Lark、Discord、QQ 等）提供通用的基础设施逻辑，
各平台只需实现平台特定的消息收发抽象方法即可。

包含：
- BotBaseUser(BaseUser): Bot 公共基类
- 文件读取工具方法
- 模型选择/清空确认处理
- 消息循环模板
"""

from __future__ import annotations

import json
import os
import time
from abc import abstractmethod
from typing import TYPE_CHECKING, Callable

from config import get_config, CONFIG_FILE
from logger import log
from user.user import BaseUser

if TYPE_CHECKING:
    from host.momoka import Momoka


class BotBaseUser(BaseUser):
    """Bot 平台公共基类。

    所有 Bot 平台（Lark、Discord、QQ）继承此类。
    子类只需实现 _send_platform_message、_send_platform_file、消息队列相关的抽象方法。

    此类提供：
    - _run_main_loop: 通用消息循环（含模型选择、清空确认、斜杠命令、Agent 调用等）
    - 文件读取工具方法（_read_file_content / _try_read_text / _read_office）
    - _handle_model_choice / _handle_clear_confirmation / _handle_end_command
    - _create_slash_handler / _fetch_models_for_model
    - send_output / send_error 的通用实现
    """

    interface_type: str = 'bot'

    def __init__(self):
        super().__init__()
        self._agent: Momoka | None = None
        self._start_time: float = 0.0

        # 当前活跃的聊天/频道 ID（子类在收到消息时设置）
        self._active_chat_id: str | None = None

        # 已发送过欢迎消息的聊天集合
        self._welcome_sent_chats: set[str] = set()

    # ── 子类必须实现的抽象方法 ───────────────────────────────────────

    @abstractmethod
    def _send_platform_message(self, chat_id: str, text: str) -> None:
        """向平台发送文本消息。"""
        ...

    @abstractmethod
    def _send_platform_file(self, chat_id: str, file_path: str, caption: str = '') -> None:
        """向平台发送文件。"""
        ...

    @abstractmethod
    def _has_platform_message(self, chat_id: str) -> bool:
        """检查指定聊天是否有新消息。"""
        ...

    @abstractmethod
    def _get_platform_message(self, chat_id: str) -> str | None:
        """从指定聊天的队列中获取一条消息。返回 None 表示队列为空。"""
        ...

    @abstractmethod
    def _get_all_chat_ids(self) -> list[str]:
        """返回所有有消息队列的聊天 ID 列表。"""
        ...

    # ── 子类可选择覆盖的方法 ────────────────────────────────────────

    def _get_system_prompt(self) -> str:
        """获取注入 Agent 的 system 提示，子类可覆盖。"""
        return f"<You are communicating with user via {self.interface_type}>"

    def _get_welcome_message(self) -> str:
        """获取欢迎消息，子类可覆盖。"""
        return (
            f"Successfully connected to {self.interface_type}\n"
            "Welcome back! This is Momoka~\n"
            "Developed by Mikoris | For more help, type /help"
        )

    def _send_welcome_and_system(self, chat_id: str) -> None:
        """发送欢迎消息到用户和 system 提示给 Agent。"""
        if chat_id in self._welcome_sent_chats:
            return

        self._welcome_sent_chats.add(chat_id)

        # 发送欢迎消息
        welcome_msg = self._get_welcome_message()
        self._send_platform_message(chat_id, welcome_msg)
        log(f'{self.interface_type} | welcome message sent to {chat_id}')

        # 发送 system 消息给 Agent（不触发响应）
        if self._agent is not None:
            system_msg = self._get_system_prompt()
            self._agent._model._ctx.history.append({
                'role': 'system',
                'content': system_msg
            })
            self._agent._model._ctx._meta.append({})
            log(f'{self.interface_type} | system message added to agent history')

    # ── 通用消息循环 ────────────────────────────────────────────────

    def _run_main_loop(self) -> None:
        """通用消息循环。

        轮询所有聊天的消息队列 → 欢迎消息 → 模型选择处理 → 清空确认 →
        斜杠命令处理 → Agent 调用。
        """
        from user.commands import SlashCommandHandler

        # 创建适配器和斜杠命令处理器
        adapter = self._create_interaction_adapter()
        callbacks = adapter.create_slash_callbacks()
        slash_handler = SlashCommandHandler(callbacks)

        # 状态
        waiting_for_model_choice = False
        pending_models: list[str] = []
        waiting_for_clear_confirmation = False

        while True:
            # 查找有消息的聊天
            active_chat_id = None
            for chat_id in self._get_all_chat_ids():
                if self._has_platform_message(chat_id):
                    active_chat_id = chat_id
                    break

            if active_chat_id is None:
                self._on_no_message()
                continue

            user_message = self._get_platform_message(active_chat_id)
            if user_message is None:
                continue

            # 设置当前活跃聊天
            self._active_chat_id = active_chat_id

            log(f'{self.interface_type} | processing: {user_message[:60]}...')

            if self._agent is None:
                continue

            # 首条消息：欢迎 + system 提示
            self._send_welcome_and_system(active_chat_id)

            # 模型选择等待状态
            if waiting_for_model_choice:
                waiting_for_model_choice = False
                if self._handle_model_choice(user_message, pending_models):
                    continue

            # 清空确认等待状态
            if waiting_for_clear_confirmation:
                waiting_for_clear_confirmation = False
                if self._handle_clear_confirmation(user_message):
                    continue

            # 斜杠命令处理
            if user_message.strip().startswith('/'):
                # /model 命令需要特殊处理（异步等待用户输入数字）
                if user_message.strip() == '/model':
                    models = self._fetch_models_for_model()
                    if models:
                        pending_models = models
                        waiting_for_model_choice = True
                        self._send_model_list(active_chat_id, models)
                        continue
                    else:
                        self._send_platform_message(active_chat_id, 'No models available or failed to fetch.')
                        continue

                handled, skill_name = slash_handler.handle(user_message)
                if handled:
                    if skill_name == '__end__':
                        self._handle_end_command()
                        break
                    if skill_name == '__init__':
                        self._on_init_command()
                        continue
                    if skill_name == '__clear_ask__':
                        waiting_for_clear_confirmation = True
                        continue
                    if skill_name is not None:
                        self._handle_skill_trigger(skill_name)
                        continue
                    continue

            # 修复历史
            repaired = self._agent.repair_history()
            if repaired:
                log(f'{self.interface_type} | repair_history: filled in {repaired} orphaned tool_calls')

            # 调用 Agent
            try:
                result = self._agent.send(user_message)
                self.session.update(result)
                if result.is_finish:
                    self._agent.finish_task()
                    self.on_task_finish()
            except Exception as e:
                log(f'{self.interface_type} | agent error: {e}')
                self._send_platform_message(active_chat_id, f"Error:\n{str(e)}")

    def _on_no_message(self) -> None:
        """没有消息时的等待逻辑，子类可覆盖以实现事件驱动等待。"""
        time.sleep(0.1)

    def _on_init_command(self) -> None:
        """处理 /init 命令。"""
        if self._agent is not None:
            try:
                success = self._agent.initialize_project()
                if success:
                    self._send_platform_message(self._active_chat_id, 'AGENTS.md generated successfully')
                else:
                    self._send_platform_message(self._active_chat_id, 'Failed to generate AGENTS.md')
            except Exception as e:
                self._send_platform_message(self._active_chat_id, f'Failed to generate AGENTS.md: {e}')

    def _handle_skill_trigger(self, skill_name: str) -> None:
        """处理 Skill 加载。"""
        log(f'{self.interface_type} | skill trigger: {skill_name}')
        if self._agent is not None:
            load_result = self._agent.load_skill(skill_name)
            if load_result.success:
                self._send_platform_message(self._active_chat_id, f'Load Skill: {skill_name}')
                log(f'{self.interface_type} (skill inject): {skill_name}')
            else:
                self._send_platform_message(self._active_chat_id, f'Non-existent command or skill: {skill_name}')

    # ── 交互适配器创建（子类需实现） ─────────────────────────────────

    @abstractmethod
    def _create_interaction_adapter(self) -> object:
        """创建交互适配器实例，应返回包含 create_slash_callbacks() 方法的对象。"""
        ...

    # ── 模型选择 ─────────────────────────────────────────────────────

    def _fetch_models_for_model(self) -> list[str]:
        """获取可用模型列表。"""
        try:
            from model.model import fetch_available_models
            return fetch_available_models()
        except Exception as e:
            log(f'{self.interface_type} | failed to fetch models: {e}')
            return []

    def _send_model_list(self, chat_id: str, models: list[str]) -> None:
        """发送模型列表供用户选择。"""
        cfg = get_config()
        current = cfg.get('model', '')
        model_list = '\n'.join([
            f"  {i + 1}. {m}{' [current]' if m == current else ''}"
            for i, m in enumerate(models)
        ])
        self._send_platform_message(
            chat_id,
            f"Available models:\n{model_list}\n\n"
            f"Please reply with the model number (1-{len(models)}) or leave blank to cancel."
        )

    def _handle_model_choice(self, user_message: str, models: list[str]) -> bool:
        """处理用户的模型选择输入。

        Returns:
            True 表示已处理，False 表示输入无效（作为普通消息继续处理）
        """
        user_input = user_message.strip()

        if not user_input:
            self._send_platform_message(self._active_chat_id, 'Cancelled.')
            return True

        try:
            choice = int(user_input)
        except ValueError:
            return False

        if choice < 1 or choice > len(models):
            self._send_platform_message(
                self._active_chat_id,
                f'Invalid selection. Please enter a number between 1 and {len(models)}.'
            )
            return True

        selected_model = models[choice - 1]
        cfg = get_config()
        current = cfg.get('model', '')

        if selected_model == current:
            self._send_platform_message(self._active_chat_id, f'Model unchanged: {selected_model}')
            return True

        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                config_data = json.load(f)
            config_data['model'] = selected_model
            with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
                json.dump(config_data, f, ensure_ascii=False, indent=2)
            log(f'{self.interface_type} | model changed: {current} → {selected_model}')
        except Exception as e:
            self._send_platform_message(self._active_chat_id, f'Failed to save model: {e}')
            return True

        return True

    # ── 清空确认 ─────────────────────────────────────────────────────

    def _handle_clear_confirmation(self, user_message: str) -> bool:
        """处理用户对清空操作的确认回复。

        Returns:
            True 表示已处理
        """
        user_input = user_message.strip().lower()
        if user_input in ('y', 'yes', '确认', '是'):
            try:
                if self._agent is not None:
                    self._agent.clear_context()
                    self.session.reset()
                    self.on_clear_context()
                self._send_platform_message(self._active_chat_id, 'Context cleared.')
            except Exception as e:
                self._send_platform_message(self._active_chat_id, f'Failed to clear context: {e}')
        else:
            self._send_platform_message(self._active_chat_id, 'Cancelled.')
        return True

    # ── 文件读取工具方法 ─────────────────────────────────────────────

    @staticmethod
    def _read_file_content(file_path: str, file_name: str) -> str | None:
        """读取文件内容为文本。

        Returns:
            文件文本内容，如果不是文本文件返回 None
        """
        # 检查文件大小（限制 10MB）
        max_size = 10 * 1024 * 1024
        try:
            file_size = os.path.getsize(file_path)
            if file_size > max_size:
                return f"[File too large: {file_size / 1024 / 1024:.2f}MB, max 10MB]"
        except OSError:
            return None

        ext = os.path.splitext(file_name)[1].lower()

        # 文本扩展名集合
        text_extensions = {
            '.txt', '.md', '.py', '.js', '.ts', '.html', '.css', '.json',
            '.xml', '.yaml', '.yml', '.csv', '.log', '.ini', '.conf',
            '.sh', '.bash', '.zsh', '.fish', '.ps1', '.bat', '.cmd',
            '.c', '.cpp', '.h', '.hpp', '.java', '.go', '.rs', '.swift',
            '.kt', '.scala', '.rb', '.php', '.pl', '.lua', '.r', '.m',
            '.sql', '.dockerfile', '.makefile', '.cmake', '.gradle',
            '.vue', '.jsx', '.tsx', '.svelte', '.less', '.scss', '.sass',
        }
        office_extensions = {'.docx', '.xlsx'}

        if ext in office_extensions:
            return BotBaseUser._read_office_file(file_path, ext)
        if ext in text_extensions or ext not in {
            '.pdf', '.doc', '.xls', '.ppt', '.zip', '.rar', '.7z',
            '.tar', '.gz', '.exe', '.dll', '.so', '.dylib',
        }:
            return BotBaseUser._try_read_text_file(file_path)

        return None

    @staticmethod
    def _try_read_text_file(file_path: str) -> str | None:
        """尝试以多种编码读取文本文件。"""
        for encoding in ['utf-8', 'gbk', 'gb2312', 'latin-1', 'cp1252']:
            try:
                with open(file_path, 'r', encoding=encoding) as f:
                    return f.read()
            except (UnicodeDecodeError, UnicodeError):
                continue
            except Exception as e:
                log(f'bot_base | read text error ({encoding}): {e}')
                return None
        return None

    @staticmethod
    def _read_office_file(file_path: str, ext: str) -> str | None:
        """读取 Office 文档内容。"""
        try:
            if ext == '.docx':
                from docx import Document
                doc = Document(file_path)
                paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
                return '\n'.join(paragraphs) if paragraphs else None
            elif ext == '.xlsx':
                import openpyxl
                wb = openpyxl.load_workbook(file_path, data_only=True)
                lines = []
                for sheet in wb.worksheets:
                    lines.append(f'--- Sheet: {sheet.title} ---')
                    for row in sheet.iter_rows(values_only=True):
                        row_text = ' | '.join(str(c) if c is not None else '' for c in row)
                        if row_text.strip():
                            lines.append(row_text)
                return '\n'.join(lines) if lines else None
        except ImportError:
            log(f'bot_base | missing library for reading {ext} files')
            return None
        except Exception as e:
            log(f'bot_base | read office file error: {e}')
            return None
        return None

    # ── BaseUser 接口实现 ────────────────────────────────────────────

    def get_input(self) -> str:
        """等待并获取用户输入（阻塞式）。"""
        while True:
            for chat_id in self._get_all_chat_ids():
                msg = self._get_platform_message(chat_id)
                if msg is not None:
                    return msg
            time.sleep(0.1)

    def send_output(self, message: str, role: str = 'BOT') -> None:
        """向用户输出消息。"""
        log(f'{self.interface_type} ({role}) | {message}')
        if self._active_chat_id:
            if role == 'BOT':
                self._send_platform_message(self._active_chat_id, message)
            else:
                self._send_platform_message(self._active_chat_id, f"[{role}]\n{message}")

    def send_error(self, message: str) -> None:
        """输出错误消息。"""
        log(f'{self.interface_type} ERROR | {message}')
        if self._active_chat_id:
            self._send_platform_message(self._active_chat_id, f"Error: {message}")

    def send_file(self, file_path: str, caption: str = '') -> None:
        """向用户发送一个文件。"""
        log(f'{self.interface_type} | send_file: {file_path} | caption: {caption}')

        if not os.path.exists(file_path):
            log(f'{self.interface_type} | send_file error: file not found: {file_path}')
            self.send_error(f'File not found: {file_path}')
            return

        if self._active_chat_id:
            self._send_platform_file(self._active_chat_id, file_path, caption)

    # ── 会话生命周期 ─────────────────────────────────────────────────

    def set_agent(self, agent: Momoka) -> None:
        """设置关联的 Agent 实例。"""
        self._agent = agent

    def on_task_finish(self) -> None:
        """任务完成回调。"""
        log(f'{self.interface_type} | task finished')

    def on_session_end(self, input_tokens: int, output_tokens: int,
                       round_count: int, elapsed: float) -> None:
        """会话结束回调。"""
        mins = int(elapsed // 60)
        secs = int(elapsed % 60)
        time_str = f'{mins}min {secs}s' if mins else f'{secs}s'
        log(f'{self.interface_type} | session end '
            f'({time_str} | Input: {input_tokens} tokens | '
            f'Output: {output_tokens} tokens | {round_count}R)')

    def _handle_end_command(self) -> None:
        """处理 /end 命令。"""
        elapsed = time.time() - self._start_time
        self.on_session_end(
            self.session.input_tokens,
            self.session.output_tokens,
            self.session.round_count,
            elapsed
        )
