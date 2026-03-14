from config import get_config
from script.logger import log, chat_log, user_log
from openai import OpenAI
from openai import (
    APIConnectionError,
    APITimeoutError,
    AuthenticationError,
    PermissionDeniedError,
    RateLimitError,
    APIStatusError,
)
import sys
import threading
import itertools
import time


def _openai_call(fn, *args, **kwargs):
    """统一执行 OpenAI SDK 调用，捕获常见错误并通过 user_log 告知用户。

    Returns:
        API 响应对象，出错时返回 None。
    """
    try:
        return fn(*args, **kwargs)
    except AuthenticationError as e:
        user_log(f'认证失败: API Key 无效或已过期。({e})', role='ERROR')
    except PermissionDeniedError as e:
        user_log(f'权限不足: 该 API Key 无权访问指定模型或接口。({e})', role='ERROR')
    except RateLimitError as e:
        user_log(f'速率限制: 请求过于频繁或额度已耗尽，请稍后重试。({e})', role='ERROR')
    except APITimeoutError as e:
        user_log(f'请求超时: 服务端未在规定时间内响应，请检查网络或稍后重试。({e})', role='ERROR')
    except APIConnectionError as e:
        user_log(f'连接失败: 无法连接到 API 服务，请检查网络或 base_url 配置。({e})', role='ERROR')
    except APIStatusError as e:
        user_log(f'API 错误 {e.status_code}：{e.message}', role='ERROR')
    except Exception as e:
        user_log(f'未知错误：{type(e).__name__}: {e}', role='ERROR')
    return None


# ── 终端等待动画 ──────────────────────────────────────────────────────────
class Spinner:
    """在 API 请求期间显示旋转动画，仅在交互式终端下启用。"""
    _enabled = sys.stdout.isatty()

    def __init__(self):
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._spin, daemon=True)

    def _spin(self):
        for ch in itertools.cycle(['-', '\\', '|', '/']):
            if self._stop.is_set():
                break
            sys.stdout.write(f'\r{ch} ')
            sys.stdout.flush()
            time.sleep(0.25)
        sys.stdout.write('\r  \r')
        sys.stdout.flush()

    def __enter__(self):
        if self._enabled:
            self._thread.start()
        return self

    def __exit__(self, *_):
        if self._enabled:
            self._stop.set()
            self._thread.join()

# ── Tool 定义（JSON Function Call 格式）────────────────────────────────────
from script.tools_def import *


class Bot:
    def __init__(self, bot_name: str = 'null'):
        self.bot_name = bot_name
        cfg = get_config()
        self.openai = OpenAI(api_key=cfg['api_key'], base_url=cfg['base_url'])
        self._base_system: str = 'You are a helpful assistant'
        self._injected_skills: dict[str, str] = {}  # {skill_name: skill_content}
        self.history = [{'role': 'system', 'content': self._base_system}]
        # 与 history 等长的元数据列表。
        # 每个元素是一个字典，目前只用 'file_contents' 键：
        #   {'file_contents': {filename: content_str, ...}}
        # 普通消息对应的元数据为空字典 {}。
        self._meta: list[dict] = [{}]

    def message(self, message: str, role: str = 'user',
                file_contents: dict[str, str] | None = None,
                use_tools: bool = False) -> dict:
        """向模型发送消息，返回响应字典。

        Args:
            message:       发送给模型的文本。
            role:          消息角色，默认 'user'。
            file_contents: 本条消息中包含的文件内容，格式为 {filename: content}。
            use_tools:     是否传入 TOOLS 列表启用 function calling。

        Returns:
            dict，包含：
                'content': str       —— 模型的文本回复（可能为空字符串）
                'tool_calls': list   —— tool_call 对象列表（可能为空列表）
        """
        cfg = get_config()
        log_prefix = f'chat with {cfg["model"]} ({cfg["base_url"]}) as {self.bot_name}'
        log(f'{log_prefix} | input: {message}')

        kwargs: dict = dict(
            model=cfg['model'],
            messages=self.history + [{'role': role, 'content': message}],
            stream=False,
        )
        if use_tools:
            kwargs['tools'] = TOOLS
            kwargs['tool_choice'] = 'auto'

        # noinspection PyTypeChecker
        with Spinner():
            response = _openai_call(self.openai.chat.completions.create, **kwargs)

        if response is None:
            # 错误已由 _openai_call 通过 user_log(role='ERROR') 告知用户
            return {'content': '', 'tool_calls': [], 'input_tokens': 0, 'output_tokens': 0}

        choice = response.choices[0].message

        text_content: str = choice.content or ''
        tool_calls: list = choice.tool_calls or []

        log(f'{log_prefix} | output text: {text_content}')
        if tool_calls:
            for tc in tool_calls:
                log(f'{log_prefix} | tool_call: {tc.function.name}({tc.function.arguments})')

        # ── 将本轮对话写入历史（assistant 消息需含 tool_calls 字段）──────────
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

        self.history.extend([
            {'role': role, 'content': message},
            assistant_msg,
        ])
        self._meta.append({'file_contents': file_contents or {}})
        self._meta.append({})  # assistant 消息无文件内容

        chat_log(f'[{self.bot_name}] USER: {message}')
        chat_log(f'[{self.bot_name}] ASSISTANT TEXT: {text_content}')
        if tool_calls:
            chat_log(f'[{self.bot_name}] TOOL_CALLS: {[tc.function.name for tc in tool_calls]}')
        chat_log(f'[{self.bot_name}] HISTORY SNAPSHOT: {self.history}')

        return {
            'content': text_content,
            'tool_calls': tool_calls,
            'input_tokens': response.usage.prompt_tokens if response.usage else 0,
            'output_tokens': response.usage.completion_tokens if response.usage else 0,
        }

    def add_tool_result(self, tool_call_id: str, result: str,
                        file_contents: dict[str, str] | None = None):
        """将工具执行结果追加到对话历史，供下一次 message() 使用。"""
        self.history.append({
            'role': 'tool',
            'tool_call_id': tool_call_id,
            'content': result,
        })
        self._meta.append({'file_contents': file_contents or {}})

    def resume(self, use_tools: bool = True) -> dict:
        """工具执行完毕后，直接用当前历史继续推理，不插入任何 user 消息。

        调用方应在所有 add_tool_result() 完成后调用此方法。
        """
        cfg = get_config()
        log_prefix = f'chat with {cfg["model"]} ({cfg["base_url"]}) as {self.bot_name}'
        log(f'{log_prefix} | resume')

        kwargs: dict = dict(model=cfg['model'], messages=self.history, stream=False)
        if use_tools:
            kwargs['tools'] = TOOLS
            kwargs['tool_choice'] = 'auto'

        # noinspection PyTypeChecker
        with Spinner():
            response = _openai_call(self.openai.chat.completions.create, **kwargs)

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

        self.history.append(assistant_msg)
        self._meta.append({})

        chat_log(f'[{self.bot_name}] RESUME ASSISTANT TEXT: {text_content}')
        if tool_calls:
            chat_log(f'[{self.bot_name}] RESUME TOOL_CALLS: {[tc.function.name for tc in tool_calls]}')

        return {
            'content': text_content,
            'tool_calls': tool_calls,
            'input_tokens': response.usage.prompt_tokens if response.usage else 0,
            'output_tokens': response.usage.completion_tokens if response.usage else 0,
        }

    def set_system(self, system: str):
        """设置或替换 system 提示词（同时重置 base system）。"""
        self._base_system = system
        self._apply_system()

    def inject_skill(self, skill_name: str, skill_content: str):
        """将 skill 内容追加到 system prompt，finish 后可通过 clear_skills 移除。"""
        self._injected_skills[skill_name] = skill_content
        self._apply_system()
        log(f'bot.inject_skill | 注入skill: {skill_name}')

    def clear_skills(self):
        """移除所有已注入的 skill，将 system 恢复为 base system。"""
        if not self._injected_skills:
            return
        names = list(self._injected_skills.keys())
        self._injected_skills.clear()
        self._apply_system()
        log(f'bot.clear_skills | 已移除skills: {names}')

    def _apply_system(self):
        """将 base system + 所有已注入 skill 合并写入 history[0]。"""
        parts = [self._base_system]
        for name, content in self._injected_skills.items():
            parts.append(f'\n<skill: {name}>\n{content}\n</skill>')
        full_system = ''.join(parts)
        if self.history[0]['role'] == 'system':
            self.history[0]['content'] = full_system
        else:
            self.history.insert(0, {'role': 'system', 'content': full_system})
            self._meta.insert(0, {})

    def collapse_file_in_history(self, filename: str) -> int:
        """将对话历史中除最后一次之外、所有包含指定文件内容的消息折叠。

        通过 _meta 中记录的原始文件内容精确定位并替换，无需正则匹配。
        返回折叠的消息条数。
        """
        placeholder = f'[文件内容已折叠: {filename}]'
        hits = [
            i for i, m in enumerate(self._meta)
            if filename in m.get('file_contents', {})
        ]
        if len(hits) <= 1:
            return 0

        collapsed_count = 0
        for i in hits[:-1]:
            content = self._meta[i]['file_contents'][filename]
            original = self.history[i].get('content')
            if original and isinstance(original, str):
                new_content = original.replace(content, placeholder, 1)
                if new_content != original:
                    self.history[i]['content'] = new_content
                    collapsed_count += 1
                    log(f'bot.collapse_file_in_history | 折叠历史[{i}]中的文件: {filename}')
            del self._meta[i]['file_contents'][filename]

        return collapsed_count


def chat(question: str, role: str = 'user') -> str:
    """快捷函数：创建一次性 Bot 并发送单条消息（不使用 tools）。"""
    result = Bot().message(question, role, use_tools=False)
    return result['content']