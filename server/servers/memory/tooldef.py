"""
server/servers/memory/tooldef.py —— Memory tool definitions.

Covers: memorize / recall
"""

from __future__ import annotations

from config import get_config

# ── Tool definitions ───────────────────────────────────────────────────────

TOOL_DEFINITIONS: list[dict] = [
    {
        'type': 'function',
        'function': {
            'name': 'memorize',
            'description': (
                'Store information in memory.'
            ),
            'parameters': {
                'type': 'object',
                'properties': {
                    'content': {
                        'type': 'string',
                        'description': 'The information to remember.',
                    },
                    'keywords': {
                        'type': 'array',
                        'items': {'type': 'string'},
                        'description': 'A list of keywords or tags associated with this memory, for easy recall later. Use English. '
                                       'If you want to memorize something related to a specific project, '
                                       'it is recommended to include the project name and other information in the "content" field.',
                    },
                },
                'required': ['content', 'keywords'],
            },
        },
    },
    {
        'type': 'function',
        'function': {
            'name': 'recall',
            'description': (
                'Search and retrieve memories from memory.\n'
                'This tool can be used when information such as unknown user or project preferences is needed.\n'
                'Searches by keywords or content text, returning matching memories.\n'
            ),
            'parameters': {
                'type': 'object',
                'properties': {
                    'query': {
                        'oneOf': [
                            {
                                'type': 'array',
                                'items': {'type': 'string'},
                                'minItems': 1,
                            },
                        ],
                        'description': 'A list of queries (list[string]) to find relevant memories. '
                                       'Each item uses one word. '
                                       'Use English.',
                    },
                },
                'required': ['query'],
            },
        },
    },
]


# ── Availability checks ────────────────────────────────────────────────────

def is_available() -> bool:
    """Memory tools are available only when config.json memory=true."""
    cfg = get_config()
    return cfg.get('memory', False)
