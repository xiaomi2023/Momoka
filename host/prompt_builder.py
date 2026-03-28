"""
host/prompt_builder.py —— 系统提示词构建。

负责发现可用技能并组装 Momoka 的 system prompt。
"""

import os
import sys

import config
from config import get_config
from server import get_cwd


def discover_skills(cfg: dict) -> list[dict]:
    """扫描项目 skills 目录，返回所有合法技能的元数据列表（含 name/description）。"""
    skills_dir = cfg.get('skills_dir', 'skill')
    if os.path.isabs(skills_dir):
        skills_root = skills_dir
    else:
        project_root = os.environ.get('MOMOKA_PROJECT_DIR', os.path.dirname(os.path.abspath(__file__)) + '/..')
        skills_root = os.path.join(project_root, skills_dir)
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


def build_system_prompt() -> str:
    """构建并返回 Momoka 的完整 system prompt。"""
    cfg = get_config()

    if sys.platform == 'win32':
        platform_hint = f'Windows({sys.platform})'
    elif sys.platform == 'darwin':
        platform_hint = f'macOS({sys.platform})'
    else:
        platform_hint = f'Linux({sys.platform})'

    skills = discover_skills(cfg)
    if skills:
        skills_hint = '\n<skill>\n' + '\n'.join(
            f'  - {s["name"]}: {s["description"]}' if s['description']
            else f'  - {s["name"]}'
            for s in skills
        )
    else:
        skills_hint = ''

    return (
        f"You are Momoka, a work assistant. Your job is to operate users' computers and complete their requests.\n"
        f"Current location: {get_cwd()}\n"
        f"Working directory: {cfg['work_dir']}\n"
        f"OS: {platform_hint}\n"
        + (f"use {config.get_config()['language']} to communicate with user.\n"
        if config.get_config()['language'] is not None and config.get_config()['language'] != ""
        else "Communicate using the user's language.\n") +
        "- If you need to work on files outside the working directory, or perform operations that may damage the user's computer, please obtain the user's consent first.\n"
        "- When working, tell what you are doing or have done and why you are doing it. \n"
        "- Use plain text, not Markdown, when communicating with users.\n"
        "- Before performing a task, review and call up any skills that may be needed.\n"
        "- After completing all the work, call finish to deliver the results.\n"
        f"{(chr(10) + cfg['prompt']) if cfg.get('prompt') else ''}"
        f"{skills_hint}"
    )