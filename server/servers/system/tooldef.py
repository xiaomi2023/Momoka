"""
server/servers/system/tooldef.py — System tool definitions.

Covers: system_command / change_directory / finish / read_file / edit_file / replace_file / read_sheet
"""

from __future__ import annotations

from config import get_config

# ── Tool Definitions ─────────────────────────────────────────────────────────

TOOL_DEFINITIONS: list[dict] = [
    {
        'type': 'function',
        'function': {
            'name': 'system_command',
            'description': 'Execute a command in the terminal (in the working directory).',
            'parameters': {
                'type': 'object',
                'properties': {
                    'command': {'type': 'string', 'description': 'The terminal command to execute'},
                    'inputs': {
                        'type': ['string', 'array'],
                        'items': {'type': 'string'},
                        'description': 'Optional. Interactive input parameters. If a list, inputs are provided in order.'
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
            'description': 'Change the current working directory.',
            'parameters': {
                'type': 'object',
                'properties': {
                    'path': {'type': 'string', 'description': 'Target directory path'},
                },
                'required': ['path'],
            },
        },
    },
    {
        'type': 'function',
        'function': {
            'name': 'finish',
            'description': 'End the task and deliver the result to the user.',
            'parameters': {
                'type': 'object',
                'properties': {},
                'required': [],
            },
        },
    },
    {
        'type': 'function',
        'function': {
            'name': 'edit_file',
            'description': 'Overwrite the specified file with new content (creates the file if it does not exist).',
            'parameters': {
                'type': 'object',
                'properties': {
                    'file_path': {'type': 'string', 'description': 'Absolute path of the file (including extension)'},
                    'content': {'type': 'string', 'description': 'Content to write to the file'},
                    'encoding': {'type': 'string', 'description': 'File encoding', 'default': get_config()['encoding']},
                },
                'required': ['file_path', 'content'],
            },
        },
    },
    {
        'type': 'function',
        'function': {
            'name': 'replace_file',
            'description': 'Replace part of the content in a file.',
            'parameters': {
                'type': 'object',
                'properties': {
                    'file_path': {'type': 'string', 'description': 'Absolute path of the file (including extension)'},
                    'old_text': {'type': 'string', 'description': 'The original text to be replaced'},
                    'new_text': {'type': 'string', 'description': 'The new text to replace with'},
                    'encoding': {'type': 'string', 'description': 'File encoding', 'default': get_config()['encoding']},
                },
                'required': ['file_path', 'old_text', 'new_text'],
            },
        },
    },
    {
        'type': 'function',
        'function': {
            'name': 'read_file',
            'description': 'Read and return the content of the specified file.',
            'parameters': {
                'type': 'object',
                'properties': {
                    'file_path': {'type': 'string', 'description': 'Absolute path of the file (including extension)'},
                    'encoding': {'type': 'string', 'description': 'File encoding', 'default': get_config()['encoding']},
                    'mode': {
                        'type': 'string',
                        'enum': ['doc'],
                        'description': "Optional. 'doc': Read .docx file content in Markdown format.",
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
                'Read the content of a Sheet file (.xlsx/.xls).\n'
                'Reads the first Sheet if sheet_name is not specified.\n'
            ),
            'parameters': {
                'type': 'object',
                'properties': {
                    'file_path': {'type': 'string', 'description': 'Absolute path of the Sheet file (including extension)'},
                    'sheet_name': {
                        'type': 'string',
                        'description': 'Optional. The name of the Sheet to read.',
                    },
                    'sheet_mode': {
                        'type': 'string',
                        'enum': ['all', 'csv_only', 'formula_only'],
                        "description": "Reading mode: 'all' returns CSV + formulas (default), 'csv_only' returns only CSV, 'formula_only' returns only formulas.",
                        'default': 'all',
                    },
                    'range': {
                        'type': 'string',
                        'description': "Optional. Range to read, e.g., 'A1:D20'.",
                    },
                },
                'required': ['file_path'],
            },
        },
    },
]


# ── Availability Check (Always Available) ────────────────────────────────────

def is_available() -> bool:
    """System tools are always available."""
    return True
