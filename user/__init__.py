"""User package — User interaction interfaces."""

from user.user import BaseUser
from user.interactions import AskUser, TodoList, AskUserCallbacks, TodoListCallbacks

# 当前活动的用户接口类型，由 main.py 在启动时设置
_current_interface: str | None = None


def set_current_interface(interface_type: str) -> None:
    """设置当前用户接口类型。

    由 main.py 在启动时调用，用于记录当前使用的接口类型。

    Args:
        interface_type: 接口类型标识，如 'cli', 'lark', 'discord', 'headless'
    """
    global _current_interface
    _current_interface = interface_type


def get_current_interface() -> str | None:
    """获取当前用户接口类型。

    Returns:
        当前接口类型标识，如果尚未设置则返回 None
    """
    return _current_interface


__all__ = [
    'BaseUser',
    'AskUser',
    'TodoList',
    'AskUserCallbacks',
    'TodoListCallbacks',
    'set_current_interface',
    'get_current_interface',
]
