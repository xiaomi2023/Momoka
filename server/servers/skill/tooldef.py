"""
server/servers/skill/tooldef.py — Skill tool definitions.

Covers: get_skill
"""

from __future__ import annotations

# ── Tool Definitions ─────────────────────────────────────────────────────────

TOOL_DEFINITIONS: list[dict] = [
    {
        'type': 'function',
        'function': {
            'name': 'get_skill',
            'description': (
                'Load Agent Skills standard format skill files (SKILL.md) or scripts/resources within a skill when needed. '
                'Skill directory structure: <name>/SKILL.md, scripts/ (executable scripts), '
                'references/ (reference documents), assets/ (templates and binary resources).'
            ),
            'parameters': {
                'type': 'object',
                'properties': {
                    'skill_name': {
                        'type': 'string',
                        'description': 'Name of the skill',
                    },
                    'resource': {
                        'type': 'string',
                        'description': (
                            'Optional. Load additional executable scripts or documents. '
                            'Use absolute path (as shown in available resource files list) or relative path within the skill directory.'
                        ),
                    },
                },
                'required': ['skill_name'],
            },
        },
    },
]


# ── Availability Check Function (Always Available) ────────────────────────────

def is_available() -> bool:
    """Skill tools are always available."""
    return True
