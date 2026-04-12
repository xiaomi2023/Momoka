"""
server/servers/user/tooldef.py —— User interaction tool definitions.

Covers: ask_user, set_todolist, ask_option
"""

from __future__ import annotations

# ── Tool Definitions ─────────────────────────────────────────────────────────

TOOL_DEFINITIONS: list[dict] = [
    {
        'type': 'function',
        'function': {
            'name': 'ask_user',
            'description': 'Ask the user a question.',
            'parameters': {
                'type': 'object',
                'properties': {
                    'question': {'type': 'string', 'description': 'The question to ask the user'},
                },
                'required': ['question'],
            },
        },
    },
    {
        'type': 'function',
        'function': {
            'name': 'set_todolist',
            'description': 'Display a todo list. Use this tool when you need to complete a complex task.',
            'parameters': {
                'type': 'object',
                'properties': {
                    'tasks': {
                        'type': 'array',
                        'description': 'List of todo items',
                        'items': {
                            'type': 'object',
                            'properties': {
                                'title': {'type': 'string', 'description': 'Task title'},
                                'status': {
                                    'type': 'string',
                                    'enum': ['pending', 'in_progress', 'done'],
                                    'description': 'Task status: pending (to do), in_progress (in progress), done (completed)'
                                },
                            },
                            'required': ['title'],
                        },
                    },
                },
                'required': ['tasks'],
            },
        },
    },
    {
        'type': 'function',
        'function': {
            'name': 'ask_option',
            'description': 'Ask the user to select one or more options.',
            'parameters': {
                'type': 'object',
                'properties': {
                    'question': {'type': 'string', 'description': 'The question to ask the user'},
                    'options': {
                        'type': 'array',
                        'description': 'List of options',
                        'items': {
                            'type': 'object',
                            'properties': {
                                'label': {'type': 'string', 'description': 'Option display label'},
                                'description': {'type': 'string', 'description': 'Detailed description of the option'},
                            },
                            'required': ['label'],
                        },
                    },
                    'allow_multiple': {
                        'type': 'boolean',
                        'description': 'Whether to allow multiple selections, defaults to false'
                    },
                },
                'required': ['question', 'options'],
            },
        },
    },
]


# ── Availability Check (Always Available) ─────────────────────────────────────

def is_available() -> bool:
    """User tools are always available."""
    return True
