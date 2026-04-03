"""
server/servers/office_tooldef.py —— 文件与表格操作工具定义。

涵盖: read_file / edit_file / replace_file / read_sheet
"""

from __future__ import annotations

from config import get_config

# ── 工具定义 ────────────────────────────────────────────────────────────────

TOOL_DEFINITIONS: list[dict] = [
    {
        'type': 'function',
        'function': {
            'name': 'edit_file',
            'description': '用新内容覆盖指定文件（文件不存在则新建文件）。',
            'parameters': {
                'type': 'object',
                'properties': {
                    'file_path': {'type': 'string', 'description': '文件的绝对路径（含扩展名）'},
                    'content': {'type': 'string', 'description': '写入文件的内容'},
                    'encoding': {'type': 'string', 'description': '文件编码', 'default': get_config()['encoding']},
                },
                'required': ['file_path', 'content'],
            },
        },
    },
    {
        'type': 'function',
        'function': {
            'name': 'replace_file',
            'description': '对文件的部分内容进行替换。',
            'parameters': {
                'type': 'object',
                'properties': {
                    'file_path': {'type': 'string', 'description': '文件的绝对路径（含扩展名）'},
                    'old_text': {'type': 'string', 'description': '要被替换的原始文本'},
                    'new_text': {'type': 'string', 'description': '替换后的新文本'},
                    'encoding': {'type': 'string', 'description': '文件编码', 'default': get_config()['encoding']},
                },
                'required': ['file_path', 'old_text', 'new_text'],
            },
        },
    },
    {
        'type': 'function',
        'function': {
            'name': 'read_file',
            'description': '读取并返回指定文件的内容。',
            'parameters': {
                'type': 'object',
                'properties': {
                    'file_path': {'type': 'string', 'description': '文件的绝对路径（含扩展名）'},
                    'encoding': {'type': 'string', 'description': '文件编码', 'default': get_config()['encoding']},
                    'mode': {
                        'type': 'string',
                        'enum': ['doc'],
                        'description': "可选。'doc'：以 Markdown 格式读取 .docx 文件内容。",
                    },
                },
                'required': ['file_path'],
            },
        },
    },
    {
        'type': 'function',
        'function': {
            'name': 'read_sheet',
            'description': (
                '读取 Sheet 文件（.xlsx/.xls）的内容。\n'
                '不指定 sheet_name 时返回所有 Sheet 名称列表并读取第一个 Sheet。\n'
            ),
            'parameters': {
                'type': 'object',
                'properties': {
                    'file_path': {'type': 'string', 'description': 'Sheet 文件的绝对路径（含扩展名）'},
                    'sheet_name': {
                        'type': 'string',
                        'description': '可选。要读取的 Sheet 名称。',
                    },
                    'sheet_mode': {
                        'type': 'string',
                        'enum': ['all', 'csv_only', 'formula_only'],
                        'description': "读取模式：'all' 返回 CSV + 公式（默认），'csv_only' 只返回 CSV，'formula_only' 只返回公式。",
                        'default': 'all',
                    },
                    'range': {
                        'type': 'string',
                        'description': "可选。读取范围，如 'A1:D20'。",
                    },
                },
                'required': ['file_path'],
            },
        },
    },
]


# ── 条件检查函数（始终可用）─────────────────────────────────────────────────

def is_available() -> bool:
    """文件操作工具始终可用。"""
    return True
