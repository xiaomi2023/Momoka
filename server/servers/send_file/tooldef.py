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
    
    send_file 仅在 Lark 和 Discord 模式下可用，CLI 和 Headless 模式下不可用。
    通过 user 模块中设置的当前接口类型来确定。
    """
    try:
        from user import get_current_interface
        interface = get_current_interface()
        
        # 如果尚未设置（启动阶段），回退到检查配置文件
        if interface is None:
            from config import get_config
            cfg = get_config()
            interface = cfg.get('interface', 'cli')
        
        # 仅在 Lark 和 Discord 模式下可用
        return interface in ('lark', 'discord')
    except Exception:
        # 如果无法获取配置，默认不可用（安全起见）
        return False
