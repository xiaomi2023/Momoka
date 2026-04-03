"""
server/servers/ask_user.py —— 用户交互工具处理器。

涵盖: ask_user
"""

from __future__ import annotations

from server import ToolResult, ToolContext


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


# ── 工具处理器函数 ─────────────────────────────────────────────────────────

def ask_user(args: dict, ctx: ToolContext) -> ToolResult:
    question = args.get('question', '')
    reply = ctx.input_func('>> ')
    text = f'用户回复: {reply}' if reply else '用户什么都没回复。'
    return ToolResult(
        text=text,
        log_msg=question,
        log_role='QUESTION',
    )
