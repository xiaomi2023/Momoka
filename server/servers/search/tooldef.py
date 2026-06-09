"""
server/servers/search/tooldef.py — Search tool definitions.

Covers: grep / glob
"""

from __future__ import annotations

# ── Tool Definitions ─────────────────────────────────────────────────────────

TOOL_DEFINITIONS: list[dict] = [
    {
        'type': 'function',
        'function': {
            'name': 'grep',
            'description': (
                'Search for text patterns in file contents using regular expressions.\n'
                'Supports filtering by file type (e.g., *.py, *.ts, *.md).\n'
            ),
            'parameters': {
                'type': 'object',
                'properties': {
                    'pattern': {
                        'type': 'string',
                        'description': 'The regular expression pattern to search for',
                    },
                    'path': {
                        'type': 'string',
                        'description': 'Directory or file path to search in. If not specified, searches from the current location (current working directory).',
                    },
                    'glob': {
                        'type': 'string',
                        'description': 'Optional. File pattern to filter results (e.g., "*.py", "*.ts", "*.{js,ts}")',
                    },
                    'case_sensitive': {
                        'type': 'boolean',
                        'description': 'Whether the search is case-sensitive',
                        'default': False,
                    },
                    'max_results': {
                        'type': 'integer',
                        'description': 'Maximum number of results to return',
                        'default': 100,
                    },
                },
                'required': ['pattern'],
            },
        },
    },
    {
        'type': 'function',
        'function': {
            'name': 'glob',
            'description': (
                'Find files by name pattern using glob-style wildcards.\n'
                'Supports patterns like **/*.py, src/**/*.ts, etc.'
            ),
            'parameters': {
                'type': 'object',
                'properties': {
                    'pattern': {
                        'type': 'string',
                        'description': 'The glob pattern to match (e.g., "**/*.py", "src/**/*.ts")',
                    },
                    'path': {
                        'type': 'string',
                        'description': 'Root directory to search in. If not specified, searches from the current location (current working directory).',
                    },
                },
                'required': ['pattern'],
            },
        },
    },
]


# ── Availability Check (Always Available) ────────────────────────────────────

def is_available() -> bool:
    """Search tools are always available."""
    return True
