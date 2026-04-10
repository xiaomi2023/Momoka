"""
server/servers/skill/skill.py —— get_skill handler 和 skill 发现逻辑。
"""

from __future__ import annotations

import os

from logger import log
from server.types import ToolResult, ToolContext


def get_skills_root(cfg: dict) -> str:
    """获取 SKILL 根目录路径。"""
    skills_dir = cfg.get('skills_dir', 'skill')
    if os.path.isabs(skills_dir):
        return skills_dir
    project_root = os.environ.get('MOMOKA_PROJECT_DIR', '')
    return os.path.join(project_root, skills_dir)


def discover_skills(cfg: dict) -> list[dict]:
    """扫描 skills 目录，返回所有合法 skill 的元数据列表。"""
    skills_root = get_skills_root(cfg)
    found = []

    if not os.path.isdir(skills_root):
        return found

    for entry in sorted(os.listdir(skills_root)):
        skill_path = os.path.join(skills_root, entry)
        skill_md = os.path.join(skill_path, 'SKILL.md')
        if not (os.path.isdir(skill_path) and os.path.isfile(skill_md)):
            continue
        meta = {'name': entry, 'description': ''}
        try:
            with open(skill_md, 'r', encoding=cfg.get('encoding', 'utf-8')) as fh:
                lines = fh.readlines()
            if lines and lines[0].strip() == '---':
                for line in lines[1:]:
                    if line.strip() == '---':
                        break
                    if line.startswith('description:'):
                        meta['description'] = line.split(':', 1)[1].strip().strip('"\'')
                        break
        except Exception:
            pass
        found.append(meta)

    return found


def get_skill(args: dict, ctx: ToolContext) -> ToolResult:
    skill_name = args.get('skill_name', '').strip()
    resource = args.get('resource', '').strip()
    encoding = ctx.cfg.get('encoding', 'utf-8')

    skills_root = get_skills_root(ctx.cfg)
    skill_path = os.path.join(skills_root, skill_name)

    if not os.path.isdir(skill_path):
        return ToolResult(text=f'Can not find skill: {skill_name} (Path: {skill_path})')

    # ── Read single resource file ────────────────────────────────────────────
    if resource:
        # Support both absolute path and relative path
        if os.path.isabs(resource):
            target = resource
        else:
            target = os.path.join(skill_path, resource)
        
        if not os.path.isfile(target):
            available = []
            for root_, _, files_ in os.walk(skill_path):
                for f_ in files_:
                    available.append(os.path.realpath(os.path.join(root_, f_)))
            return ToolResult(
                text=(f'<Resource file not found: {resource}>\n'
                      f'Available resource files for skill {skill_name!r}:\n' +
                      '\n'.join(f'  {f}' for f in sorted(available)))
            )
        try:
            with open(target, 'r', encoding=encoding) as fh:
                content = fh.read()
            log(f'get_skill | {skill_name}/{resource} ({len(content)} chars)')
            return ToolResult(
                text=content,
                file_contents={target: content},
                log_msg=f'Read Skill: {skill_name}/{resource}',
            )
        except Exception as e:
            return ToolResult(text=f'<Failed to read resource file: {e}>')

    # ── Read SKILL.md + list available resources ─────────────────────────────
    skill_md = os.path.join(skill_path, 'SKILL.md')
    if not os.path.isfile(skill_md):
        return ToolResult(text=f'<The skill directory exists, but SKILL.md is missing: {skill_path}>')

    try:
        with open(skill_md, 'r', encoding=encoding) as fh:
            content = fh.read()

        extras = []
        for sub in ('scripts', 'references', 'assets'):
            sub_path = os.path.join(skill_path, sub)
            if os.path.isdir(sub_path):
                for fn in sorted(os.listdir(sub_path)):
                    extras.append(os.path.realpath(os.path.join(sub_path, fn)))

        suffix = ('\n\nAvailable resource files:\n' +
                  '\n'.join(f'  {e}' for e in extras)) if extras else ''

        log(f'get_skill | {skill_name}/SKILL.md ({len(content)} chars)')
        return ToolResult(
            text=content + suffix,
            file_contents={skill_md: content},
            log_msg=f'Load Skill: {skill_name}',
        )
    except Exception as e:
        return ToolResult(text=f'<Failed to read SKILL.md: {e}>')
