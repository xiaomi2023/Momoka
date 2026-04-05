"""
host/momoka.py —— Agent 编排器。

持有 Model 实例，负责 agent 循环（工具调用 → resume → 交还控制权）
以及 skill 的加载与清除。
"""

from dataclasses import dataclass

from logger import log
from model.model import Model
from server.router import execute_tool_calls
from host.prompt_builder import build_system_prompt
from server.tool_registry import get_available_tools


@dataclass
class SendResult:
    """send() 方法的返回结果。"""
    is_finish: bool          # 是否调用了 finish
    file_contents: dict      # 本轮读取的文件内容
    input_tokens: int        # 输入 token 数
    output_tokens: int       # 输出 token 数
    round_count: int         # 对话轮数


@dataclass
class SkillLoadResult:
    """load_skill() 方法的返回结果。"""
    success: bool            # 是否加载成功
    message: str             # 结果消息


@dataclass
class AgentLoopResult:
    """Agent 循环执行结果。"""
    is_finish: bool          # 是否调用了 finish
    file_contents: dict      # 本轮读取的文件内容
    input_tokens: int        # 输入 token 数
    output_tokens: int       # 输出 token 数
    round_count: int         # 对话轮数


class Momoka:
    """Momoka agent 编排器。"""

    def __init__(self, user=None, call_wrapper=None):
        """
        Args:
            user: 用户实例，用于输出日志
            call_wrapper: 可选的调用包装器，用于在 API 调用期间显示 spinner 等。
                         签名: wrapper(fn, *args, **kwargs) -> result
        """
        self._user = user
        self._model = Model(name='Momoka', user=user)
        self._model.set_system(build_system_prompt())
        self._call_wrapper = call_wrapper or (lambda fn, *a, **kw: fn(*a, **kw))

    # ── 对外接口（供 user 层调用）─────────────────────────────────────────

    def send(self, message: str,
             file_contents: dict[str, str] | None = None) -> SendResult:
        """接收用户消息，启动 agent 循环，返回循环结束时的状态。"""
        log(f'momoka.send | {message}')
        
        # 获取当前可用的工具列表
        available_tools = get_available_tools()
        
        response = self._call_wrapper(
            self._model.message,
            message,
            role='user',
            file_contents=file_contents,
            use_tools=True,
            available_tools=available_tools,
        )

        input_tokens = response.get('input_tokens', 0)
        output_tokens = response.get('output_tokens', 0)
        round_count = 1

        loop_result = self._agent_loop(
            response, file_contents or {}, input_tokens, output_tokens, round_count
        )

        return SendResult(
            is_finish=loop_result.is_finish,
            file_contents=loop_result.file_contents,
            input_tokens=loop_result.input_tokens,
            output_tokens=loop_result.output_tokens,
            round_count=loop_result.round_count,
        )

    def load_skill(self, skill_name: str) -> SkillLoadResult:
        """加载指定 skill 并注入 system prompt。"""
        from server.router import _execute_tool
        skill_result, skill_fc, _ = _execute_tool('get_skill', {'skill_name': skill_name})
        if skill_fc:
            self._model.inject_skill(skill_name, skill_result)
            log(f'momoka.load_skill | 注入: {skill_name}')
            return SkillLoadResult(success=True, message=skill_result)
        else:
            return SkillLoadResult(success=False, message=skill_result)

    def finish_task(self):
        """任务完成后清除所有已注入的 skill。"""
        self._model.clear_skills()

    def repair_history(self) -> int:
        """修复历史中的孤儿 tool_calls 消息。"""
        return self._model.repair_history()

    def _check_interrupt(self) -> bool:
        """检查是否有待处理的中断请求，若有则打印提示并返回 True。"""
        # call_wrapper 可能是 CLIUser.call_wrapper 的绑定方法，
        # 通过 __self__ 访问其 pending_interrupt 属性
        owner = getattr(self._call_wrapper, '__self__', None)
        if owner is not None and getattr(owner, 'pending_interrupt', False):
            return True
        return False

    # ── Agent 循环 ────────────────────────────────────────────────────────

    def _agent_loop(self, response: dict, file_contents: dict,
                    input_tokens: int, output_tokens: int,
                    round_count: int) -> AgentLoopResult:
        """执行工具调用循环，直到 finish 或模型返回纯文本（等待用户输入）。"""
        while True:
            text_content: str = response['content']
            tool_calls: list = response['tool_calls']
            # ── 情形A：有工具调用 ──────────────────────────────────────
            if tool_calls:
                if text_content:
                    if self._user:
                        self._user.user_log(text_content, role='BOT')

                is_finish, file_contents = execute_tool_calls(self._model, tool_calls, user=self._user)
                if is_finish:
                    log('work DONE')
                    return AgentLoopResult(
                        is_finish=True,
                        file_contents=file_contents,
                        input_tokens=input_tokens,
                        output_tokens=output_tokens,
                        round_count=round_count
                    )

                # 本轮工具执行完毕，检查是否有待处理的中断请求
                if self._check_interrupt():
                    return AgentLoopResult(
                        is_finish=False,
                        file_contents=file_contents,
                        input_tokens=input_tokens,
                        output_tokens=output_tokens,
                        round_count=round_count
                    )

                # 获取最新的可用工具列表（浏览器状态可能已改变）
                available_tools = get_available_tools()
                
                response = self._call_wrapper(
                    self._model.resume, 
                    use_tools=True,
                    available_tools=available_tools
                )
                input_tokens += response.get('input_tokens', 0)
                output_tokens += response.get('output_tokens', 0)
                round_count += 1
                continue

            # ── 情形B：纯文本，交还控制权给用户 ───────────────────────
            if text_content:
                if self._user:
                    self._user.user_log(text_content, role='BOT')
            return AgentLoopResult(
                is_finish=False,
                file_contents=file_contents,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                round_count=round_count
            )
