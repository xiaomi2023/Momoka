"""Servers package - 各工具服务器模块。"""

from __future__ import annotations

# 导入各 server 子模块
from server.servers import system
from server.servers import user
from server.servers import settings
from server.servers import skill
from server.servers import browser

__all__ = [
    'system',
    'user',
    'settings',
    'skill',
    'browser',
]
