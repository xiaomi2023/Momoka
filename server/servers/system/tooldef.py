"""
server/servers/system/tooldef.py — System tool definitions.

Covers: system_command / change_directory / read_file / write_file / replace_file / read_sheet / wait / py_exec
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
            'name': 'wait',
            'description': 'Make you sleep for a specified number of seconds.',
            'parameters': {
                'type': 'object',
                'properties': {
                    'seconds': {
                        'type': 'number',
                        'description': 'Number of seconds to sleep (supports decimals)',
                    },
                },
                'required': ['seconds'],
            },
        },
    },
    {
        'type': 'function',
        'function': {
            'name': 'write_file',
            'description': 'Overwrite the specified file with new content (creates the file if it does not exist, '
            'and automatically creates parent directories if they do not exist). \n',
            'parameters': {
                'type': 'object',
                'properties': {
                    'file_path': {'type': 'string', 'description': 'Path of the file (including extension)'},
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
            'description': 'Replace part of the content in a file.\n'
            'If you only need to modify a portion of a file, give priority to use this tool to reduce the size of the context window.',
            'parameters': {
                'type': 'object',
                'properties': {
                    'file_path': {'type': 'string', 'description': 'Path of the file (including extension)'},
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
                    'file_path': {'type': 'string', 'description': 'Path of the file (including extension)'},
                    'encoding': {'type': 'string', 'description': 'File encoding', 'default': get_config()['encoding']},
                    'mode': {
                        'type': 'string',
                        'enum': ['doc'],
                        'description': "Optional. 'doc': Read .docx file content in Markdown format. This may not work for other file types."
                                       "If you already have Skills for processing doc documents, use Skills first.",
                    },
                    'start_line': {
                        'type': 'integer',
                        'description': 'Optional. The starting line number (1-based) to read from.',
                    },
                    'end_line': {
                        'type': 'integer',
                        'description': 'Optional. The ending line number (1-based, inclusive) to read up to.',
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
                'If you already have Skills for processing sheet files, use Skills first.'
            ),
            'parameters': {
                'type': 'object',
                'properties': {
                    'file_path': {'type': 'string', 'description': 'Path of the Sheet file (including extension)'},
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
    {
        'type': 'function',
        'function': {
            'name': 'py_exec',
            'description': 'Execute a Python code snippet.\n'
                           'The code will run in an unknown location, so do not use this tool to read or modify files.\n'
                           'The parameters and execution results will not be visible to the user.',
            'parameters': {
                'type': 'object',
                'properties': {
                    'code': {
                        'type': 'string',
                        'description': 'The Python code to execute.',
                    },
                },
                'required': ['code'],
            },
        },
    },
]


# ── Availability Check (Always Available) ────────────────────────────────────

def is_available() -> bool:
    """System tools are always available."""
    return True
