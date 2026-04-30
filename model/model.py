"""
model/model.py —— 模型调用层。

负责与 OpenAI 兼容 API 通信（发送消息、resume）。
历史与上下文管理委托给 model.context.Context。
"""

from config import get_config
from logger import log, chat_log
from model.context import Context

from openai import OpenAI
from openai import (
    APIConnectionError,
    APITimeoutError,
    AuthenticationError,
    PermissionDeniedError,
    RateLimitError,
    APIStatusError,
)


def _openai_call(fn, user=None, *args, **kwargs):
    """统一执行 OpenAI SDK 调用，捕获常见错误并通过 user_log 告知用户。

    Args:
        fn: OpenAI SDK 函数
        user: 用户实例，用于输出错误日志
        *args, **kwargs: 传递给 fn 的参数

    Returns:
        API 响应对象，出错时返回 None。
    """
    try:
        return fn(*args, **kwargs)
    except AuthenticationError as e:
        if user:
            user.user_log(f'\nAuthentication failed: API Key is invalid or expired. ({e})', role='ERROR')
    except PermissionDeniedError as e:
        if user:
            user.user_log(f'\nPermission denied: This API Key does not have access to the specified model or endpoint. ({e})', role='ERROR')
    except RateLimitError as e:
        if user:
            user.user_log(f'\nRate limit exceeded: Too many requests or quota exhausted, please try again later. ({e})', role='ERROR')
    except APITimeoutError as e:
        if user:
            user.user_log(f'\nRequest timed out: The server did not respond in time, please check your network or try again later. ({e})', role='ERROR')
    except APIConnectionError as e:
        if user:
            user.user_log(f'\nConnection failed: Unable to reach the API service, please check your network or base_url configuration. ({e})', role='ERROR')
    except APIStatusError as e:
        if user:
            user.user_log(f'\nAPI error {e.status_code}: {e.message}', role='ERROR')
    except Exception as e:
        if user:
            user.user_log(f'\nUnknown error: {type(e).__name__}: {e}', role='ERROR')
    return None


# ── Model ─────────────────────────────────────────────────────────────────

class Model:
    """模型调用层。持有 Context，负责与 API 通信。"""

    def __init__(self, name: str = 'null', user=None):
        self.name = name
        self._user = user
        cfg = get_config()
        self._client = OpenAI(api_key=cfg['api_key'], base_url=cfg['base_url'], timeout=3600)
        self._ctx = Context()

    # ── 代理 Context 的公共接口（供 host 层直接访问）─────────────────────
    @property
    def history(self):
        return self._ctx.history

    def set_system(self, system: str):
        self._ctx.set_system(system)

    def inject_skill(self, skill_name: str, skill_content: str):
        self._ctx.inject_skill(skill_name, skill_content)

    def clear_skills(self):
        self._ctx.clear_skills()

    def clear_history(self):
        """清空对话历史，仅保留 system 消息。"""
        self._ctx.clear_history()

    def repair_history(self) -> int:
        return self._ctx.repair_history()

    def add_tool_result(self, tool_call_id: str, result: str):
        self._ctx.add_tool_result(tool_call_id, result)

    # ── API 调用 ──────────────────────────────────────────────────────────

    def message(self, message: str, role: str = 'user',
                use_tools: bool = False,
                available_tools: list[dict] | None = None,
                disable_thinking: bool = True) -> dict:
        """向模型发送消息，返回响应字典。

        Args:
            message: 用户消息内容
            role: 消息角色，默认为 'user'
            use_tools: 是否使用工具
            available_tools: 可用工具列表，由 Host 层提供
            disable_thinking: 是否禁用思考链（DeepSeek-R1 等模型）

        Returns:
            dict，包含 content / tool_calls / input_tokens / output_tokens / interrupted
        """
        cfg = get_config()
        log_prefix = f'chat with {cfg["model"]} ({cfg["base_url"]}) as {self.name}'
        log(f'{log_prefix} | input: {message}')

        kwargs: dict = dict(
            model=cfg['model'],
            messages=self._ctx.history + [{'role': role, 'content': message}],
            stream=False,
        )

        # 添加 thinking 参数（禁用思考链）
        if disable_thinking:
            kwargs['extra_body'] = {"thinking": {"type": "disabled"}}

        if use_tools and available_tools:
            kwargs['tools'] = available_tools
            kwargs['tool_choice'] = 'auto'

        response = _openai_call(self._client.chat.completions.create, user=self._user, **kwargs)

        if response is None:
            return {'content': '', 'tool_calls': [], 'input_tokens': 0, 'output_tokens': 0}

        choice = response.choices[0].message
        text_content: str = choice.content or ''
        tool_calls: list = choice.tool_calls or []

        log(f'{log_prefix} | output text: {text_content}')
        if tool_calls:
            for tc in tool_calls:
                log(f'{log_prefix} | tool_call: {tc.function.name}({tc.function.arguments})')

        self._ctx.append_user(message)
        self._ctx.append_assistant(text_content, tool_calls)

        chat_log(f'[{self.name}] USER: {message}')
        chat_log(f'[{self.name}] ASSISTANT TEXT: {text_content}')
        if tool_calls:
            chat_log(f'[{self.name}] TOOL_CALLS: {[tc.function.name for tc in tool_calls]}')
        chat_log(f'[{self.name}] HISTORY SNAPSHOT: {self._ctx.history}')

        return {
            'content': text_content,
            'tool_calls': tool_calls,
            'input_tokens': response.usage.prompt_tokens if response.usage else 0,
            'output_tokens': response.usage.completion_tokens if response.usage else 0,
        }

    def resume(self, use_tools: bool = True,
               available_tools: list[dict] | None = None,
               disable_thinking: bool = True) -> dict:
        """工具执行完毕后，直接用当前历史继续推理，不插入任何 user 消息。

        Args:
            use_tools: 是否使用工具
            available_tools: 可用工具列表，由 Host 层提供
            disable_thinking: 是否禁用思考链（DeepSeek-R1 等模型）

        Returns:
            dict，包含 content / tool_calls / input_tokens / output_tokens
        """
        cfg = get_config()
        log_prefix = f'chat with {cfg["model"]} ({cfg["base_url"]}) as {self.name}'
        log(f'{log_prefix} | resume')

        kwargs: dict = dict(model=cfg['model'], messages=self._ctx.history, stream=False)

        # 添加 thinking 参数（禁用思考链）
        if disable_thinking:
            kwargs['extra_body'] = {"thinking": {"type": "disabled"}}

        if use_tools and available_tools:
            kwargs['tools'] = available_tools
            kwargs['tool_choice'] = 'auto'

        response = _openai_call(self._client.chat.completions.create, user=self._user, **kwargs)

        if response is None:
            return {'content': '', 'tool_calls': [], 'input_tokens': 0, 'output_tokens': 0}

        choice = response.choices[0].message
        text_content: str = choice.content or ''
        tool_calls: list = choice.tool_calls or []

        log(f'{log_prefix} | resume output text: {text_content}')
        if tool_calls:
            for tc in tool_calls:
                log(f'{log_prefix} | tool_call: {tc.function.name}({tc.function.arguments})')

        assistant_msg: dict = {'role': 'assistant', 'content': text_content}
        if tool_calls:
            assistant_msg['tool_calls'] = [
                {
                    'id': tc.id,
                    'type': 'function',
                    'function': {'name': tc.function.name, 'arguments': tc.function.arguments},
                }
                for tc in tool_calls
            ]
        self._ctx.append_assistant_raw(assistant_msg)

        chat_log(f'[{self.name}] RESUME ASSISTANT TEXT: {text_content}')
        if tool_calls:
            chat_log(f'[{self.name}] RESUME TOOL_CALLS: {[tc.function.name for tc in tool_calls]}')

        return {
            'content': text_content,
            'tool_calls': tool_calls,
            'input_tokens': response.usage.prompt_tokens if response.usage else 0,
            'output_tokens': response.usage.completion_tokens if response.usage else 0,
        }


def chat(question: str, role: str = 'user') -> str:
    """快捷函数：创建一次性 Model 并发送单条消息（不使用 tools）。"""
    result = Model().message(question, role, use_tools=False)
    return result['content']


def fetch_available_models() -> list[str]:
    """从 API 拉取所有可用模型列表。

    使用与 Model 类相同的配置（api_key / base_url / timeout），
    集中管理 OpenAI 客户端的创建，避免在各个地方重复创建。

    Returns:
        排好序的 model id 字符串列表，请求失败时返回空列表。
    """
    try:
        cfg = get_config()
        client = OpenAI(api_key=cfg['api_key'], base_url=cfg['base_url'], timeout=3600)
        models = client.models.list()
        return sorted(m.id for m in models.data)
    except Exception:
        return []