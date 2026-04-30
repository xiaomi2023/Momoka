"""
server/servers/settings/tooldef.py — Settings tool definitions.

Covers: set_wait / set_read_limits
"""

from __future__ import annotations

from config import get_config

# ── Tool definitions ───────────────────────────────────────────────────────

TOOL_DEFINITIONS: list[dict] = [
    {
        'type': 'function',
        'function': {
            'name': 'set_wait',
            'description': (
                'Set the maximum timeout duration (seconds) for operations.\n'
                "target='default' adjusts the general timeout (default 10 seconds), affecting almost all operations except file downloads "
                "(system_command, py_exec, browser interaction, and Office document reading, etc).\n"
                "target='download' adjusts the browser file download timeout (default 60 seconds), affecting browse_download only.\n"
            ),
            'parameters': {
                'type': 'object',
                'properties': {
                    'seconds': {'type': 'integer', 'description': 'Timeout duration in seconds'},
                    'target': {
                        'type': 'string',
                        'enum': ['default', 'download'],
                        'description': 'The timeout target to adjust.',
                        'default': 'default',
                    },
                },
                'required': ['seconds'],
            },
        },
    },
    {
        'type': 'function',
        'function': {
            'name': 'set_read_limits',
            'description': (
                'Set the maximum number of lines and maximum file size that the read_file tool is allowed to read. '
                'Default limits are 1000 lines / 100 KB. Upper limits are 50000 lines / 5120 KB (5 MB); values exceeding these will be clamped to the upper limits.'
            ),
            'parameters': {
                'type': 'object',
                'properties': {
                    'max_lines': {
                        'type': 'integer',
                        'description': 'Maximum number of lines allowed to read (upper limit 50000)',
                    },
                    'max_size_kb': {
                        'type': 'integer',
                        'description': 'Maximum file size allowed to read, in KB (upper limit 5120)',
                    },
                },
                'required': [],
            },
        },
    },
]


# ── Availability checks (always available) ─────────────────────────────────

def is_available() -> bool:
    """Settings tools are always available."""
    return True
