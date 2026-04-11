"""
user/user.py —— 用户交互抽象接口与会话状态管理。

定义 BaseUser 抽象基类，规定所有交互形式（CLI、GUI、API等）
必须实现的接口，方便未来扩展其他交互方式。
"""

from abc import ABC, abstractmethod
from typing import Any


class Session:
    """会话状态管理器，封装 token 统计、轮数计算、文件记录等。"""

    def __init__(self):
        self.file_contents: dict[str, str] = {}
        self.input_tokens = 0
        self.output_tokens = 0
        self.round_count = 0

    def update(self, result: dict | Any) -> None:
        """根据 Agent 返回结果更新会话状态。
        
        Args:
            result: Agent 返回结果，可以是 dict 或具有相应属性的对象
        """
        # 兼容 dict 和 dataclass
        if isinstance(result, dict):
            self.input_tokens += result.get('input_tokens', 0)
            self.output_tokens += result.get('output_tokens', 0)
            self.round_count += result.get('round_count', 0)
            self.file_contents = result.get('file_contents', {})
        else:
            self.input_tokens += getattr(result, 'input_tokens', 0)
            self.output_tokens += getattr(result, 'output_tokens', 0)
            self.round_count += getattr(result, 'round_count', 0)
            self.file_contents = getattr(result, 'file_contents', {})

    def reset(self) -> None:
        """重置会话状态。"""
        self.file_contents = {}
        self.input_tokens = 0
        self.output_tokens = 0
        self.round_count = 0


class BaseUser(ABC):
    """用户交互抽象基类。"""
    
    # 接口类型标识，子类应覆盖此属性
    interface_type: str = 'base'

    def __init__(self):
        self.session = Session()

    @abstractmethod
    def get_input(self) -> str:
        """从用户获取一条输入，返回字符串。"""
        ...

    @abstractmethod
    def send_output(self, message: str, role: str = 'BOT') -> None:
        """向用户输出一条消息。"""
        ...

    @abstractmethod
    def send_error(self, message: str) -> None:
        """向用户输出一条错误消息。"""
        ...

    def send_file(self, file_path: str, caption: str = '') -> None:
        """向用户发送一个文件（Discord/Lark 支持，CLI 默认只记录日志）。

        Args:
            file_path: 文件的绝对路径
            caption: 可选的伴随消息
        """
        # 默认实现：只记录日志，子类可以覆盖此方法实现真正的文件发送
        self.user_log(f'[send_file] {file_path}' + (f' | {caption}' if caption else ''))

    def user_log(self, message: str, end: str = '\n', role: str = 'LOG') -> None:
        """向用户输出日志消息（带角色标签）。
        
        Args:
            message: 日志内容
            end: 行尾字符
            role: 角色标签，影响颜色 (BOT, ERROR, BROWSER, SHELL, etc.)
        """
        self.send_output(message, role=role)

    def on_task_finish(self) -> None:
        """任务完成时的回调，子类可选择性覆盖。"""
        pass

    def on_clear_context(self) -> None:
        """清空上下文时的回调，子类可选择性覆盖以输出提示。"""
        pass

    def on_session_end(self, input_tokens: int, output_tokens: int,
                       round_count: int, elapsed: float) -> None:
        """会话结束时的回调，子类可选择性覆盖。"""
        pass
