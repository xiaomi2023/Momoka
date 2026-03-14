"""
prompt_builder.py —— 系统提示词构建。

负责发现可用技能并组装 Momoka 的 system prompt。
"""

import os
import sys

import config
from config import get_config
from script.system import get_cwd


def discover_skills(cfg: dict) -> list[dict]:
    """扫描项目 skills 目录，返回所有合法技能的元数据列表（含 name/description）。"""
    skills_dir = cfg.get('skills_dir', 'skill')
    # 优先用绝对路径；否则以 config.py 所在的项目根目录为基准，
    # 而不是 work_dir（work_dir 是用户工作目录，不是项目目录）。
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
        platform_hint = f'Windows（{sys.platform}）'
    elif sys.platform == 'darwin':
        platform_hint = f'macOS（{sys.platform}）'
    else:
        platform_hint = f'Linux（{sys.platform}）'

    skills = discover_skills(cfg)
    if skills:
        skills_hint = '\n<可用skill>\n' + '\n'.join(
            f'  - {s["name"]}: {s["description"]}' if s['description']
            else f'  - {s["name"]}'
            for s in skills
        )
    else:
        skills_hint = ''

    return (
        f"你是 Momoka，一个工作助理。你需要操作用户的电脑并完成需求。\n"
        f"当前目录: {get_cwd()}\n"
        f"工作目录（基准）: {cfg['work_dir']}\n"
        f"操作系统: {platform_hint}\n"
        f"用{config.get_config()['language']}与用户沟通\n"
        "规则: \n" +
        (f"- 称呼用户为\"{cfg['user_call']}\"。\n" if cfg['user_call'] is not None else "") +
        "- 优先在工作目录中进行操作；如需操作工作目录之外的文件，请先通过 ask_user 征得同意。\n"
        "- 工作时告知你正在做或做了什么以及为什么这样做。\n"
        "- 执行任务前先查看并调用可能会用到的skill。\n"
        "- 完成所有工作后，调用 finish 交付成果。\n"
        f"{(chr(10) + cfg['prompt']) if cfg.get('prompt') else ''}"
        f"{skills_hint}"
    )