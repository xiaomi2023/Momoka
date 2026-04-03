"""
server/servers/settings_tooldef.py —— 设置工具定义。

涵盖: set_wait / set_read_limits
"""

from __future__ import annotations

from config import get_config

# ── 工具定义 ────────────────────────────────────────────────────────────────

TOOL_DEFINITIONS: list[dict] = [
    {
        'type': 'function',
        'function': {
            'name': 'set_wait',
            'description': (
                '设置操作的最大超时时长（秒）。\n'
                "target='default' 调整通用超时（默认 10 秒），影响所有浏览器操作和命令执行。\n"
                "target='download' 调整浏览器文件下载超时（默认 60 秒），仅影响 browse_download。\n"
                '下载大文件前应先将 download 超时调高。'
            ),
            'parameters': {
                'type': 'object',
                'properties': {
                    'seconds': {'type': 'integer', 'description': '超时时长（秒）'},
                    'target': {
                        'type': 'string',
                        'enum': ['default', 'download'],
                        'description': '要调整的超时目标。',
                        'default': 'default',
                    },
                },
                'required': ['seconds'],
            },
        },
    },
    {
        'type': 'function',
        'function': {
            'name': 'set_read_limits',
            'description': (
                '设置 read_file 工具允许读取的文件最大行数和最大体积。'
                '默认限制为 1000 行 / 100 KB。上限分别为 50000 行 / 5120 KB（5 MB），超出部分自动截断到上限。'
                '当需要读取较大文件时，可先调用此工具调高限制，再调用 read_file。'
            ),
            'parameters': {
                'type': 'object',
                'properties': {
                    'max_lines': {
                        'type': 'integer',
                        'description': '允许读取的最大行数（上限 50000）',
                    },
                    'max_size_kb': {
                        'type': 'integer',
                        'description': '允许读取的最大文件体积，单位 KB（上限 5120）',
                    },
                },
                'required': [],
            },
        },
    },
]


# ── 条件检查函数（始终可用）─────────────────────────────────────────────────

def is_available() -> bool:
    """设置工具始终可用。"""
    return True
