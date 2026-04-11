"""
host/skill_manager.py —— Skill 加载与管理。

负责加载 Skill 并注入到模型上下文，以及清除已加载的 Skill。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from logger import log

if TYPE_CHECKING:
    from model.model import Model


@dataclass
class SkillLoadResult:
    """Return result from load_skill() method."""
    success: bool            # Whether loading succeeded
    message: str             # Result message


class SkillManager:
    """Skill 管理器，负责加载、注入和清除 Skill。"""

    def __init__(self, model: Model) -> None:
        self._model = model

    def load_skill(self, skill_name: str) -> SkillLoadResult:
        """加载指定的 Skill 并注入到系统提示词。

        Args:
            skill_name: Skill 名称

        Returns:
            SkillLoadResult 包含加载结果
        """
        from server.router import _execute_tool
        from server.types import ToolContext
        from config import get_config

        cfg = get_config()
        ctx = ToolContext(cfg=cfg, input_func=input)
        result = _execute_tool('get_skill', {'skill_name': skill_name}, ctx)

        # result is a ToolResult object
        skill_text = result.text
        has_file_contents = bool(result.file_contents)

        if has_file_contents:
            self._model.inject_skill(skill_name, skill_text)
            log(f'skill_manager.load_skill | Injected: {skill_name}')
            return SkillLoadResult(success=True, message=skill_text)
        else:
            return SkillLoadResult(success=False, message=skill_text)

    def clear_skills(self) -> None:
        """清除模型中所有已加载的 Skill。"""
        self._model.clear_skills()
        log('skill_manager.clear_skills | All skills cleared')
