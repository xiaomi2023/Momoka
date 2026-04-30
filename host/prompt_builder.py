"""
host/prompt_builder.py —— 系统提示词构建。

负责组装 Momoka 的 system prompt，SKILL 发现逻辑已下沉到 server 层。
"""

import os
import sys
from datetime import datetime

import config
from config import get_config
from server import get_cwd
from server.servers.skill.skill import discover_skills


def _read_prompt_file(filename: str) -> str:
    """从 host/prompt 目录读取 prompt 文件内容。"""
    prompt_dir = os.path.join(os.path.dirname(__file__), 'prompt')
    filepath = os.path.join(prompt_dir, filename)
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return f.read()
    except FileNotFoundError:
        return ''
    except Exception:
        return ''


def _get_agent_content(cfg: dict) -> str:
    """检查 work_dir 下是否存在 AGENTS.md，存在则返回其内容，否则返回 '(NULL)'。"""
    work_dir = cfg.get('work_dir', '')
    if not work_dir:
        return '(NULL)'
    agent_path = os.path.join(work_dir, 'AGENTS.md')
    try:
        with open(agent_path, 'r', encoding='utf-8') as f:
            content = f.read().strip()
            return content if content else '(NULL)'
    except (FileNotFoundError, IOError):
        return '(NULL)'


def build_system_prompt() -> str:
    """构建并返回 Momoka 的完整 system prompt。"""
    cfg = get_config()

    # 读取 platform_warning.md 文件
    platform_warning = _read_prompt_file('platform_warning.md')

    # 平台提示：使用平台原始名称，更准确
    platform_names = {
        'win32': 'Windows',
        'darwin': 'macOS',
        'linux': 'Linux',
        'linux2': 'Linux',
    }
    platform_name = platform_names.get(sys.platform, sys.platform)
    platform_hint = f'{platform_name}({sys.platform})'

    skills = discover_skills(cfg)
    if skills:
        skills_hint = '\nAvailable Skills:\n' + '\n'.join(
            f'  - {s["name"]}: {s["description"]}' if s['description']
            else f'  - {s["name"]}'
            for s in skills
        )
    else:
        skills_hint = '(The Skills list is empty)'

    # 读取 system.md 文件作为基础 prompt
    system_prompt = _read_prompt_file('system.md')

    # 获取 AGENTS.md 内容，替换 {AGENT} 占位符
    agent_content = _get_agent_content(cfg)
    system_prompt = system_prompt.replace('{AGENT}', agent_content)

    # 获取当前时间
    current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    return (
        f"{system_prompt}\n\n"
        f"### Other Information\n"
        f"Current Time: {current_time}\n"
        f"Current location: {get_cwd()}\n"
        f"Working directory: {cfg['work_dir']}\n"
        f"OS: {platform_hint}\n"
        f"{platform_warning}\n"
        f"{skills_hint}"
    )
