"""
server/servers/skill_tooldef.py —— Skill 工具定义。

涵盖: get_skill
"""

from __future__ import annotations

# ── 工具定义 ────────────────────────────────────────────────────────────────

TOOL_DEFINITIONS: list[dict] = [
    {
        'type': 'function',
        'function': {
            'name': 'get_skill',
            'description': (
                '在需要时加载 Agent Skills 标准格式的skill文件（SKILL.md）或skill内的脚本/资源文件。'
                'skill目录结构: <name>/SKILL.md、scripts/（可执行脚本）、'
                'references/（参考文档）、assets/（模板及二进制资源）。'
                '需要执行脚本或读取额外文档时，用 resource=\'scripts/xxx.py\' 等再次调用。'
            ),
            'parameters': {
                'type': 'object',
                'properties': {
                    'skill_name': {
                        'type': 'string',
                        'description': 'skill名称',
                    },
                    'resource': {
                        'type': 'string',
                        'description': (
                            '可选。skill目录内的相对路径。'
                        ),
                    },
                },
                'required': ['skill_name'],
            },
        },
    },
]


# ── 条件检查函数（始终可用）─────────────────────────────────────────────────

def is_available() -> bool:
    """Skill 工具始终可用。"""
    return True
