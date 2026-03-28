"""
server/servers/skill.py —— get_skill 处理器。
"""

from __future__ import annotations

import os

from logger import log
from server import ToolResult, ToolContext


def get_skill(args: dict, ctx: ToolContext) -> ToolResult:
    skill_name = args.get('skill_name', '').strip()
    resource = args.get('resource', '').strip()
    encoding = ctx.cfg.get('encoding', 'utf-8')

    skills_dir = ctx.cfg.get('skills_dir', 'skill')
    if os.path.isabs(skills_dir):
        skills_root = skills_dir
    else:
        project_root = os.environ.get('MOMOKA_PROJECT_DIR', '')
        skills_root = os.path.join(project_root, skills_dir)

    skill_path = os.path.join(skills_root, skill_name)

    if not os.path.isdir(skill_path):
        return ToolResult(text=f'Can not find skill: {skill_name} (Path: {skill_path})')

    # ── 读取单个资源文件 ──────────────────────────────────────────────────
    if resource:
        target = os.path.join(skill_path, resource)
        if not os.path.isfile(target):
            available = []
            for root_, _, files_ in os.walk(skill_path):
                for f_ in files_:
                    available.append(os.path.join(root_, f_))
            return ToolResult(
                text=(f'未找到资源文件: {resource}\n'
                      f'skill {skill_name!r} 中可用文件:\n' +
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
            return ToolResult(text=f'读取资源文件失败: {e}')

    # ── 读取 SKILL.md + 列出可用资源 ─────────────────────────────────────
    skill_md = os.path.join(skill_path, 'SKILL.md')
    if not os.path.isfile(skill_md):
        return ToolResult(text=f'skill目录存在但缺少 SKILL.md: {skill_path}')

    try:
        with open(skill_md, 'r', encoding=encoding) as fh:
            content = fh.read()

        extras = []
        for sub in ('scripts', 'references', 'assets'):
            sub_path = os.path.join(skill_path, sub)
            if os.path.isdir(sub_path):
                for fn in sorted(os.listdir(sub_path)):
                    extras.append(os.path.realpath(os.path.join(sub_path, fn)))

        suffix = ('\n\n可用资源文件（使用 resource 参数加载）:\n' +
                  '\n'.join(f'  {e}' for e in extras)) if extras else ''

        log(f'get_skill | {skill_name}/SKILL.md ({len(content)} chars)')
        return ToolResult(
            text=content + suffix,
            file_contents={skill_md: content},
            log_msg=f'Load Skill: {skill_name}',
        )
    except Exception as e:
        return ToolResult(text=f'读取 SKILL.md 失败: {e}')