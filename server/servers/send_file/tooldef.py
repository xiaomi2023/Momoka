"""
server/servers/send_file/tooldef.py — Send File tool definition.

定义 send_file 工具的 JSON Schema，供 LLM 使用。
"""

from __future__ import annotations


# ── Tool Definitions ─────────────────────────────────────────────────────────

TOOL_DEFINITIONS: list[dict] = [
    {
        'type': 'function',
        'function': {
            'name': 'send_file',
            'description': (
                'Send a file to the user.'
            ),
            'parameters': {
                'type': 'object',
                'properties': {
                    'file_path': {
                        'type': 'string',
                        'description': 'Absolute path of the file to send (including extension)',
                    },
                    'caption': {
                        'type': 'string',
                        'description': 'Optional. A brief description or message to accompany the file.',
                    },
                },
                'required': ['file_path'],
            },
        },
    },
]


# ── Availability Check ───────────────────────────────────────────────────────

def is_available() -> bool:
    """检查 send_file 工具是否可用。

    send_file 始终可用。Bot 平台（Lark/Discord/QQ）以附件形式发送文件，
    CLI/Headless 模式下读取文件内容以文本形式返回给用户。
    """
    return True

