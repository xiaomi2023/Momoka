"""
server/servers/ask_user_tooldef.py —— 用户交互工具定义。

涵盖: ask_user
"""

from __future__ import annotations

# ── 工具定义 ────────────────────────────────────────────────────────────────

TOOL_DEFINITIONS: list[dict] = [
    {
        'type': 'function',
        'function': {
            'name': 'ask_user',
            'description': '在有问题时向用户提问，等待用户回复后继续。',
            'parameters': {
                'type': 'object',
                'properties': {
                    'question': {'type': 'string', 'description': '向用户提出的问题'},
                },
                'required': ['question'],
            },
        },
    },
]


# ── 条件检查函数（始终可用）─────────────────────────────────────────────────

def is_available() -> bool:
    """ask_user 始终可用。"""
    return True
