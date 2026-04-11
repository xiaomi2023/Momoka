"""
user/commands.py —— 命令的纯业务逻辑层。

所有平台（CLI、Lark、Discord、Slack）共用此模块。
平台特定的渲染逻辑通过回调接口注入。
"""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass
from typing import Callable

from config import get_config


@dataclass
class SlashCommandCallbacks:
    """斜杠命令的回调接口，由具体平台实现。"""
    
    send_message: Callable[[str], None]
    """发送消息到用户界面（平台负责渲染格式）"""
    
    get_session_data: Callable[[], dict]
    """获取 session 数据，返回 dict 包含:
    - input_tokens: int
    - output_tokens: int
    - round_count: int
    - start_time: float
    """
    
    get_config: Callable[[], dict]
    """获取当前静态配置 (config.json)"""
    
    get_working_config: Callable[[], dict]
    """获取运行时配置 (working_config.json)"""
    
    update_config: Callable[[str, object], bool]
    """更新配置项，返回 True 表示成功。
    Args:
        key: 配置键名
        value: 配置值
    Returns:
        是否更新成功
    """
    
    fetch_models: Callable[[], list[str]]
    """从 API 拉取可用模型列表"""
    
    initialize_project: Callable[[], bool]
    """初始化项目，生成 AGENTS.md，返回是否成功"""
    
    load_skill: Callable[[str], object]
    """加载指定 Skill，返回 load_result 对象（包含 success 属性）"""


class SlashCommandHandler:
    """斜杠命令处理器，纯业务逻辑，所有平台共用。"""
    
    def __init__(self, callbacks: SlashCommandCallbacks):
        self.callbacks = callbacks
    
    def handle(self, cmd: str) -> tuple[bool, str | None]:
        """处理 / 开头的命令。
        
        Args:
            cmd: 用户输入的命令（应已确认以 / 开头）
            
        Returns:
            (handled, skill_name)
            handled: True 表示已处理（主循环应 continue 或走 skill 分支）
            skill_name: 非 None 时表示需要强制触发该技能
        """
        cmd = cmd.strip()
        
        # /end - 结束会话（由主循环处理，这里只返回标记）
        if cmd == '/end':
            return True, '__end__'
        
        # /usage - 显示用量统计
        if cmd == '/usage':
            self._handle_usage()
            return True, None
        
        # /config - 显示配置
        if cmd == '/config':
            self._handle_config()
            return True, None
        
        # /working_config - 显示运行时配置
        if cmd == '/working_config':
            self._handle_working_config()
            return True, None
        
        # /help - 显示帮助
        if cmd == '/help':
            self._handle_help()
            return True, None
        
        # /model - 切换模型
        if cmd == '/model':
            self._handle_model()
            return True, None
        
        # /set - 修改配置
        if cmd == '/set' or cmd.startswith('/set '):
            self._handle_set(cmd)
            return True, None
        
        # /init - 初始化项目
        if cmd == '/init':
            self._handle_init()
            return True, '__init__'
        
        # /skill_name - 加载 Skill
        m = re.fullmatch(r'/([\w\-]+)', cmd)
        if m:
            return True, m.group(1).strip()
        
        # 未知命令
        if cmd.startswith('/'):
            self.callbacks.send_message(f'Unknown command: {cmd}')
            return True, None
        
        return False, None
    
    def _handle_usage(self) -> None:
        """处理 /usage 命令。"""
        session = self.callbacks.get_session_data()
        elapsed = time.time() - session['start_time']
        mins = int(elapsed // 60)
        secs = int(elapsed % 60)
        time_str = f'{mins}min {secs}s' if mins else f'{secs}s'
        
        msg = (
            f"Usage: Input {session['input_tokens']} tokens | "
            f"Output {session['output_tokens']} tokens | "
            f"{session['round_count']}R | "
            f"Time taken {time_str}"
        )
        self.callbacks.send_message(msg)
    
    def _handle_config(self) -> None:
        """处理 /config 命令。"""
        try:
            cfg = self.callbacks.get_config()
            # 隐藏 API Key
            display = {k: ('***' if 'key' in k.lower() else v) for k, v in cfg.items()}
            msg = json.dumps(display, ensure_ascii=False, indent=2)
            self.callbacks.send_message(msg)
        except Exception as e:
            self.callbacks.send_message(f'Failed in reading config: {e}')
    
    def _handle_working_config(self) -> None:
        """处理 /working_config 命令。"""
        try:
            wc = self.callbacks.get_working_config()
            msg = json.dumps(wc, ensure_ascii=False, indent=2)
            self.callbacks.send_message(msg)
        except Exception as e:
            self.callbacks.send_message(f'Failed in reading working_config: {e}')
    
    def _handle_help(self) -> None:
        """处理 /help 命令。"""
        help_text = (
            "  /end                — End session and show usage statistics\n"
            "  /usage              — Show current token usage\n"
            "  /config             — Show config\n"
            "  /working_config     — Show working_config\n"
            "  /set <key> <value>  — Modify configuration in config\n"
            "  /model              — Select and switch the current model\n"
            "  /skill_name         — Load specified skill\n"
            "  /init               — Generate AGENTS.md for current project\n"
            "  /help               — Show help"
        )
        self.callbacks.send_message(help_text)
    
    def _handle_model(self) -> None:
        """处理 /model 命令。"""
        models = self.callbacks.fetch_models()
        if not models:
            self.callbacks.send_message('No models available or failed to fetch.')
            return

        cfg = self.callbacks.get_config()
        current = cfg.get('model', '')

        # 打印模型列表
        model_list = '\n'.join([
            f"  {i+1}. {m}{' [current]' if m == current else ''}"
            for i, m in enumerate(models)
        ])

        self.callbacks.send_message(
            f"Available models:\n{model_list}\n\n"
            f"Please reply with the model number (1-{len(models)}) or leave blank to cancel."
        )

        # 等待用户选择（平台特定的实现会通过回调处理）
        # 注意：这个方法的实际选择逻辑需要平台在消息循环中处理
        # 这里只是发送提示，具体的等待和更新逻辑由平台层实现
        # TODO: 未来可以添加一个回调让用户选择后自动更新
    
    def _handle_set(self, cmd: str) -> None:
        """处理 /set 命令。"""
        parts = cmd[5:].strip().split(None, 1)
        
        if len(parts) != 2:
            config_help = (
                "Available configuration options:\n\n"
                "  api_key    — LLM API key for authentication\n"
                "  base_url   — API base URL endpoint\n"
                "  model      — Model name to use (e.g., gpt-4o)\n"
                "  work_dir   — Default working directory path\n"
                "  encoding   — File encoding (default: utf-8)\n"
                "  fold       — Fold history file content in output (true/false)\n"
                "  mute_log   — List of roles to mute in logs (e.g., [\"SHELL\", \"BROWSER\"])\n"
                "  prompt     — Additional system prompt text\n\n"
                "Usage: /set <key> <value>"
            )
            self.callbacks.send_message(config_help)
            return
        
        key, raw_value = parts
        
        # 验证 key 是否存在
        cfg = self.callbacks.get_config()
        if key not in cfg:
            allowed = ', '.join(sorted(cfg.keys()))
            self.callbacks.send_message(
                f'Unknown config key: {key}\nAllowed keys: {allowed}'
            )
            return
        
        # 类型推断
        value = self._infer_type(raw_value)
        
        # 更新配置
        success = self.callbacks.update_config(key, value)
        if success:
            display_value = '***' if 'key' in key.lower() else repr(value)
            self.callbacks.send_message(f'config updated: {key} = {display_value}')
        else:
            self.callbacks.send_message('Failed to write config')
    
    def _handle_init(self) -> None:
        """处理 /init 命令。"""
        self.callbacks.send_message('Generating AGENTS.md...')
        try:
            success = self.callbacks.initialize_project()
            if success:
                self.callbacks.send_message('AGENTS.md generated successfully')
            else:
                self.callbacks.send_message('Failed to generate AGENTS.md')
        except Exception as e:
            self.callbacks.send_message(f'Failed to generate AGENTS.md: {e}')
    
    @staticmethod
    def _infer_type(s: str) -> bool | int | float | str:
        """将字符串 value 推断为合适的 Python 类型。"""
        if s.lower() == 'true':
            return True
        if s.lower() == 'false':
            return False
        try:
            return int(s)
        except ValueError:
            pass
        try:
            return float(s)
        except ValueError:
            pass
        return s
