"""
server/servers/system_tooldef.py —— 系统工具定义。

涵盖: system_command / change_directory / finish
"""

from __future__ import annotations

# ── 工具定义 ────────────────────────────────────────────────────────────────

TOOL_DEFINITIONS: list[dict] = [
    {
        'type': 'function',
        'function': {
            'name': 'system_command',
            'description': '在用户的终端执行命令。',
            'parameters': {
                'type': 'object',
                'properties': {
                    'command': {'type': 'string', 'description': '要执行的终端命令'},
                    'inputs': {
                        'type': ['string', 'array'],
                        'items': {'type': 'string'},
                        'description': '可选。如果命令需要交互式输入（如确认、输入参数），在此提供。若是列表则按顺序输入。'
                    }
                },
                'required': ['command'],
            },
        },
    },
    {
        'type': 'function',
        'function': {
            'name': 'change_directory',
            'description': '切换当前工作目录。',
            'parameters': {
                'type': 'object',
                'properties': {
                    'path': {'type': 'string', 'description': '目标目录路径'},
                },
                'required': ['path'],
            },
        },
    },
    {
        'type': 'function',
        'function': {
            'name': 'finish',
            'description': '结束工作并向用户交付。',
            'parameters': {
                'type': 'object',
                'properties': {},
                'required': [],
            },
        },
    },
]


# ── 条件检查函数（始终可用）─────────────────────────────────────────────────

def is_available() -> bool:
    """系统工具始终可用。"""
    return True
