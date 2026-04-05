"""
user/headless/headless.py —— 无头模式用户交互实现。

提供两种无头交互模式：
1. StdioHeadlessUser - 基于标准输入输出（stdin/stdout），适合管道和子进程
2. FileHeadlessUser - 基于文件读写，适合异步通信和跨进程交互

通信协议：
- 输入：JSON Lines 格式，每行一个 JSON 对象
- 输出：JSON Lines 格式，结构化日志和状态
"""

import json
import sys
import time
import os
from pathlib import Path
from typing import TextIO

from logger import log, new_log
from user.user import BaseUser


class HeadlessUser(BaseUser):
    """无头模式基类，提供 JSON Lines 格式的输入输出。
    
    子类需实现 get_input_stream() 和 get_output_stream() 方法。
    """

    def __init__(self):
        super().__init__()
        self._agent = None
        self._start_time = 0.0

    def set_agent(self, agent):
        """设置关联的 Agent 实例。"""
        self._agent = agent

    def get_input_stream(self) -> TextIO:
        """获取输入流，子类实现。"""
        raise NotImplementedError

    def get_output_stream(self) -> TextIO:
        """获取输出流，子类实现。"""
        raise NotImplementedError

    def _write_json(self, data: dict) -> None:
        """写出一条 JSON 记录到输出流。"""
        stream = self.get_output_stream()
        stream.write(json.dumps(data, ensure_ascii=False) + '\n')
        stream.flush()

    def run(self) -> None:
        """启动无头会话循环。
        
        输入格式（JSON Lines）：
            {"type": "message", "content": "..."}  - 用户消息
            {"type": "command", "command": "end"}  - 结束会话
            {"type": "command", "command": "usage"} - 显示用量
            {"type": "command", "command": "config"} - 显示配置
        
        输出格式（JSON Lines）：
            {"type": "log", "role": "BOT", "content": "..."}
            {"type": "log", "role": "TOOL", "content": "..."}
            {"type": "error", "content": "..."}
            {"type": "usage", "input_tokens": ..., "output_tokens": ..., "rounds": ..., "time": "..."}
            {"type": "config", "config": {...}}
            {"type": "session_end"} - 会话结束
        """
        if self._agent is None:
            raise RuntimeError("Agent not set. Call set_agent() before run().")

        new_log()
        log('headless_start')

        self._start_time = time.time()
        self.session.reset()

        # 输出会话开始标记
        self._write_json({
            'type': 'session_start',
            'mode': 'headless'
        })

        while True:
            try:
                user_message = self.get_input()
            except (EOFError, KeyboardInterrupt):
                break

            if not user_message:
                continue

            # 解析输入
            try:
                msg = json.loads(user_message)
            except json.JSONDecodeError:
                # 非 JSON 格式，当作普通消息处理
                msg = {'type': 'message', 'content': user_message}

            msg_type = msg.get('type', 'message')

            if msg_type == 'command':
                command = msg.get('command', '')
                if command == 'end':
                    self._emit_session_end()
                    log('headless_end')
                    break
                elif command == 'usage':
                    self._emit_usage()
                elif command == 'config':
                    self._emit_config()
                else:
                    self._write_json({
                        'type': 'error',
                        'content': f'Unknown command: {command}'
                    })
                continue

            if msg_type == 'message':
                content = msg.get('content', '')
                if not content:
                    continue

                # 修复历史中可能残留的孤儿 tool_calls 消息
                repaired = self._agent.repair_history()
                if repaired:
                    log(f'headless | repair_history: 补全了 {repaired} 个孤儿 tool_result')

                # 处理特殊命令（如 /set, /model 等）
                if content.startswith('/'):
                    handled = self._handle_slash_command(content)
                    if handled:
                        continue

                # 普通用户消息，交给 agent 处理
                result = self._agent.send(
                    content,
                    file_contents=self.session.file_contents
                )

                self.session.update(result)

                if result.is_finish:
                    self._agent.finish_task()
                    self._write_json({
                        'type': 'task_finish'
                    })

    def get_input(self) -> str:
        """从输入流读取一行 JSON。"""
        stream = self.get_input_stream()
        line = stream.readline()
        if not line:
            raise EOFError
        return line.strip()

    def send_output(self, message: str, role: str = 'BOT') -> None:
        """向输出流写一条日志记录。"""
        self._write_json({
            'type': 'log',
            'role': role,
            'content': message
        })

    def send_error(self, message: str) -> None:
        """向输出流写一条错误记录。"""
        self._write_json({
            'type': 'error',
            'content': message
        })

    def user_log(self, message: str, end: str = '\n', role: str = 'LOG') -> None:
        """输出日志消息（带角色标签）。"""
        from config import get_config

        # mute_log 过滤
        if role in get_config().get('mute_log', []):
            return

        self._write_json({
            'type': 'log',
            'role': role,
            'content': message
        })

    def on_task_finish(self) -> None:
        """任务完成时的回调。"""
        self._write_json({
            'type': 'task_finish'
        })

    def on_session_end(self, input_tokens: int, output_tokens: int,
                       round_count: int, elapsed: float) -> None:
        """会话结束时的回调。"""
        self._emit_usage()
        self._write_json({
            'type': 'session_end'
        })

    def _emit_usage(self) -> None:
        """输出用量统计。"""
        elapsed = time.time() - self._start_time
        mins = int(elapsed // 60)
        secs = int(elapsed % 60)
        time_str = f'{mins}min {secs}s' if mins else f'{secs}s'

        self._write_json({
            'type': 'usage',
            'input_tokens': self.session.input_tokens,
            'output_tokens': self.session.output_tokens,
            'rounds': self.session.round_count,
            'time': time_str
        })

    def _emit_config(self) -> None:
        """输出当前配置。"""
        try:
            from config import get_config
            cfg = get_config()
            # 隐藏 API Key
            display = {k: ('***' if 'key' in k.lower() else v) for k, v in cfg.items()}
            self._write_json({
                'type': 'config',
                'config': display
            })
        except Exception as e:
            self._write_json({
                'type': 'error',
                'content': f'Failed to read config: {str(e)}'
            })

    def _emit_session_end(self) -> None:
        """输出会话结束标记。"""
        self.on_session_end(
            self.session.input_tokens,
            self.session.output_tokens,
            self.session.round_count,
            time.time() - self._start_time
        )

    def _handle_slash_command(self, content: str) -> bool:
        """处理 slash 命令。
        
        Returns:
            True 表示已处理，False 表示未处理
        """
        content = content.strip()

        if content == '/end':
            self._emit_session_end()
            return True

        if content == '/usage':
            self._emit_usage()
            return True

        if content == '/config':
            self._emit_config()
            return True

        # 其他 slash 命令暂不处理，交给 agent
        return False


class StdioHeadlessUser(HeadlessUser):
    """基于标准输入输出的无头模式。
    
    适合场景：
    - 管道通信（如 echo '{"type":"message","content":"你好"}' | python main.py --headless stdio）
    - 子进程调用
    - Docker 容器
    """

    def get_input_stream(self) -> TextIO:
        return sys.stdin

    def get_output_stream(self) -> TextIO:
        return sys.stdout


class FileHeadlessUser(HeadlessUser):
    """基于文件读写的无头模式。
    
    适合场景：
    - 异步通信
    - 跨进程交互
    - 服务集成
    
    使用方式：
        1. 创建输入文件（如 input.txt）
        2. 程序持续读取输入文件，处理后删除已读取的行
        3. 程序持续追加写入输出文件（如 output.txt）
    """

    def __init__(self, input_file: str, output_file: str, poll_interval: float = 0.1):
        """
        Args:
            input_file: 输入文件路径
            output_file: 输出文件路径
            poll_interval: 轮询间隔（秒）
        """
        super().__init__()
        self.input_file = Path(input_file)
        self.output_file = Path(output_file)
        self.poll_interval = poll_interval
        self._input_offset = 0
        self._output_fd = None

        # 确保输出文件存在
        self.output_file.parent.mkdir(parents=True, exist_ok=True)
        if not self.output_file.exists():
            self.output_file.touch()

    def get_input_stream(self) -> TextIO:
        """读取输入文件的新内容。"""
        # 等待输入文件存在
        while not self.input_file.exists():
            time.sleep(self.poll_interval)

        # 读取输入文件
        with open(self.input_file, 'r', encoding='utf-8') as f:
            f.seek(self._input_offset)
            lines = f.readlines()
            self._input_offset = f.tell()

        if not lines:
            # 没有新内容，等待
            time.sleep(self.poll_interval)
            # 返回空字符串，调用方会继续循环
            import io
            return io.StringIO('')

        # 返回读取的行
        import io
        return io.StringIO(''.join(lines))

    def get_output_stream(self) -> TextIO:
        """获取输出文件描述符（追加模式）。"""
        if self._output_fd is None:
            self._output_fd = open(self.output_file, 'a', encoding='utf-8')
        return self._output_fd

    def close(self) -> None:
        """关闭文件描述符。"""
        if self._output_fd:
            self._output_fd.close()
            self._output_fd = None
