"""
host/initializer.py —— 项目初始化。

负责为当前项目生成 AGENTS.md 文件。
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

from logger import log

if TYPE_CHECKING:
    from user.user import BaseUser


class Initializer:
    """项目初始化器，负责为当前项目生成 AGENTS.md 文件。"""

    def __init__(
        self,
        send_func,
        finish_task_func,
    ) -> None:
        """
        Args:
            send_func: 等同于 Momoka.send 的函数
            finish_task_func: 等同于 Momoka.finish_task 的函数
        """
        self._send = send_func
        self._finish_task = finish_task_func

    def initialize_project(self) -> bool:
        """为当前项目生成 AGENTS.md 文件。

        Returns:
            True 如果生成成功，False 如果生成失败
        """
        # 读取提示词模板
        init_prompt_path = os.path.join(
            os.path.dirname(__file__),
            'prompt',
            'init.md',
        )

        try:
            with open(init_prompt_path, 'r', encoding='utf-8') as f:
                init_prompt = f.read()
        except FileNotFoundError:
            log('initializer.initialize_project | Error: init prompt template not found')
            return False
        except Exception as e:
            log(f'initializer.initialize_project | Error: Failed to read init prompt: {e}')
            return False

        log('initializer.initialize_project | Generating AGENTS.md')

        try:
            # 使用 Agent 循环处理生成任务
            self._send(init_prompt)

            # 清理 skills
            self._finish_task()

            log('initializer.initialize_project | Generation completed')
            return True

        except Exception as e:
            log(f'initializer.initialize_project | Error: {e}')
            return False

