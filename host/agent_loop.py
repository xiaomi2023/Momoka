"""
host/agent_loop.py —— Agent 循环执行器。

负责工具调用循环：执行工具 → 检查中断 → resume → 直到返回纯文本。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Callable

from logger import log
from server.router import execute_tool_calls
from server.tool_registry import get_available_tools

if TYPE_CHECKING:
    from model.model import Model
    from user.user import BaseUser


@dataclass
class AgentLoopResult:
    """Agent loop execution result."""
    input_tokens: int        # Input token count
    output_tokens: int       # Output token count
    round_count: int         # Number of conversation rounds


class AgentLoopRunner:
    """Agent 循环执行器，管理工具调用循环和中断检查。"""

    def __init__(
        self,
        model: Model,
        user: BaseUser | None = None,
        call_wrapper: Callable | None = None,
    ) -> None:
        self._model = model
        self._user = user
        self._call_wrapper = call_wrapper or (lambda fn, *a, **kw: fn(*a, **kw))

    def run(
        self,
        initial_response: dict,
        input_tokens: int = 0,
        output_tokens: int = 0,
        round_count: int = 1,
    ) -> AgentLoopResult:
        """执行 agent 循环直到模型返回纯文本响应。

        Args:
            initial_response: 模型对初始消息的响应
            input_tokens: 已消耗的 input token 数
            output_tokens: 已消耗的 output token 数
            round_count: 当前对话轮数

        Returns:
            AgentLoopResult 包含最终执行结果
        """
        response = initial_response

        while True:
            text_content: str = response['content']
            tool_calls: list = response['tool_calls']

            # ── Case A: Has tool calls ─────────────────────────────────
            if tool_calls:
                if text_content and self._user:
                    self._user.user_log(text_content, role='BOT')

                execute_tool_calls(self._model, tool_calls, user=self._user)

                # Tool execution completed this round, check for pending interrupt requests
                if self._check_interrupt():
                    return AgentLoopResult(
                        input_tokens=input_tokens,
                        output_tokens=output_tokens,
                        round_count=round_count,
                    )

                # Get latest available tools (browser state may have changed)
                available_tools = get_available_tools()

                response = self._call_wrapper(
                    self._model.resume,
                    use_tools=True,
                    available_tools=available_tools,
                )
                input_tokens += response.get('input_tokens', 0)
                output_tokens += response.get('output_tokens', 0)
                round_count += 1
                continue

            # ── Case B: Plain text, return control to user ───────────────
            if text_content and self._user:
                self._user.user_log(text_content, role='BOT')
            return AgentLoopResult(
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                round_count=round_count,
            )

    def _check_interrupt(self) -> bool:
        """检查是否有待处理的中断请求，如有则打印提示并返回 True。"""
        # call_wrapper might be a bound method of CLIUser.call_wrapper,
        # access its pending_interrupt attribute via __self__
        owner = getattr(self._call_wrapper, '__self__', None)
        if owner is not None and getattr(owner, 'pending_interrupt', False):
            return True
        return False

