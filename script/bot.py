from config import get_config
from script.logger import log, chat_log, user_log, _rich_available
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
import time

if _rich_available:
    from rich.console import Console
    from rich.status import Status
    _spinner_console = Console(highlight=False)


def _openai_call(fn, *args, **kwargs):
    """统一执行 OpenAI SDK 调用，捕获常见错误并通过 user_log 告知用户。

    Returns:
        API 响应对象，出错时返回 None。
    """
    try:
        return fn(*args, **kwargs)
    except AuthenticationError as e:
        user_log(f'Authentication failed: API Key is invalid or expired. ({e})', role='ERROR')
    except PermissionDeniedError as e:
        user_log(f'Permission denied: This API Key does not have access to the specified model or endpoint. ({e})', role='ERROR')
    except RateLimitError as e:
        user_log(f'Rate limit exceeded: Too many requests or quota exhausted, please try again later. ({e})', role='ERROR')
    except APITimeoutError as e:
        user_log(f'Request timed out: The server did not respond in time, please check your network or try again later. ({e})', role='ERROR')
    except APIConnectionError as e:
        user_log(f'Connection failed: Unable to reach the API service, please check your network or base_url configuration. ({e})', role='ERROR')
    except APIStatusError as e:
        user_log(f'API error {e.status_code}: {e.message}', role='ERROR')
    except Exception as e:
        user_log(f'Unknown error: {type(e).__name__}: {e}', role='ERROR')
    return None


# ── 终端等待动画 ──────────────────────────────────────────────────────────
class Spinner:
    """在 API 请求期间显示等待动画，仅在交互式终端下启用。

    有 rich 时使用 rich.Status（自带动画线程，支持动态更新文字）；
    无 rich 时降级为原始手写旋转动画。
    支持按 ESC 键中断，中断后会在当前步骤完成后交还控制权。
    """
    _enabled = sys.stdout.isatty()

    # ── rich 版消息 ────────────────────────────────────────────────────
    _MSG_NORMAL       = '[dim]Press ESC to Interrupt[/dim]'
    _MSG_INTERRUPTING = '[red]Interrupting...[/red][dim](Press Ctrl+C to force stop)[/dim]'

    def __init__(self):
        self._stop        = threading.Event()
        self._interrupted = threading.Event()
        self._input_thread: threading.Thread | None = None

        # rich 路径用到的对象
        self._status: 'Status | None' = None

        # 降级路径用到的线程
        self._spin_thread: threading.Thread | None = None

    # ── 降级：手写旋转动画（rich 不可用时）────────────────────────────
    def _spin_plain(self):
        import itertools
        for ch in itertools.cycle(['—', '\\', '|', '/']):
            if self._stop.is_set():
                break
            if self._interrupted.is_set():
                line = f'\rInterrupting...(Press Ctrl+C to force stop) {ch}'
            else:
                line = f'\r(Press ESC to Interrupt) {ch} '
            sys.stdout.write(line)
            sys.stdout.flush()
            time.sleep(0.25)
        sys.stdout.write('\r' + ' ' * 40 + '\r')
        sys.stdout.flush()

    # ── ESC 检测（Windows only，非 Windows 静默忽略）─────────────────
    def _check_input(self):
        try:
            import msvcrt
            while not self._stop.is_set():
                if msvcrt.kbhit():
                    key = msvcrt.getch()
                    if key == b'\x1b':          # ESC = 0x1b
                        self._interrupted.set()
                        if self._status is not None:
                            self._status.update(self._MSG_INTERRUPTING)
                        while msvcrt.kbhit():   # 清空剩余按键
                            msvcrt.getch()
                        break
                time.sleep(0.05)
        except Exception:
            pass

    # ── 上下文管理器 ───────────────────────────────────────────────────
    def __enter__(self):
        if not self._enabled:
            return self

        if _rich_available:
            self._status = _spinner_console.status(
                self._MSG_NORMAL,
                spinner='dots',
                spinner_style='cyan',
            )
            self._status.__enter__()
        else:
            self._spin_thread = threading.Thread(target=self._spin_plain, daemon=True)
            self._spin_thread.start()

        self._input_thread = threading.Thread(target=self._check_input, daemon=True)
        self._input_thread.start()
        return self

    def __exit__(self, *_):
        if not self._enabled:
            return

        self._stop.set()

        if _rich_available and self._status is not None:
            self._status.__exit__(None, None, None)
            self._status = None
        elif self._spin_thread is not None:
            self._spin_thread.join()

        if self._input_thread:
            self._input_thread.join(timeout=0.1)

    def is_interrupted(self) -> bool:
        """返回是否收到了中断信号。"""
        return self._interrupted.is_set()

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
        with Spinner() as spinner:
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
            'interrupted': spinner.is_interrupted(),
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
        with Spinner() as spinner:
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
            'interrupted': spinner.is_interrupted(),
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

    def repair_history(self) -> int:
        """检测并修复对话历史中孤儿 tool_calls 消息（无对应 tool_result 的情况）。

        当用户中断（ESC）导致 tool_calls 还未执行就退出时，历史里会留下一条
        assistant tool_calls 消息但没有紧随的 tool 消息，下次 API 调用会报 400。
        此方法会为每个缺失的 tool_call_id 补一条占位 tool 消息。

        Returns:
            修复的孤儿 tool_call 数量（0 表示历史无需修复）。
        """
        repaired = 0
        i = 0
        while i < len(self.history):
            msg = self.history[i]
            if msg.get('role') == 'assistant' and msg.get('tool_calls'):
                # 收集该 assistant 消息的所有 tool_call_id
                expected_ids = {tc['id'] for tc in msg['tool_calls']}
                # 收集紧随其后的 tool 消息已覆盖的 id
                j = i + 1
                covered_ids: set[str] = set()
                while j < len(self.history) and self.history[j].get('role') == 'tool':
                    covered_ids.add(self.history[j].get('tool_call_id', ''))
                    j += 1
                # 找出缺失的 id，补占位消息
                missing_ids = expected_ids - covered_ids
                if missing_ids:
                    placeholder_msgs = []
                    placeholder_metas = []
                    for tc_id in missing_ids:
                        placeholder_msgs.append({
                            'role': 'tool',
                            'tool_call_id': tc_id,
                            'content': '（已中断，工具未执行）',
                        })
                        placeholder_metas.append({})
                        repaired += 1
                    # 插入到紧随 assistant 消息之后（j 是第一个非 tool 消息的位置）
                    self.history[i + 1:i + 1] = placeholder_msgs
                    self._meta[i + 1:i + 1] = placeholder_metas
                    log(f'bot.repair_history | 补全 {len(missing_ids)} 个孤儿 tool_result: {missing_ids}')
                    i = j + len(missing_ids)
                else:
                    i = j
            else:
                i += 1
        return repaired

    def collapse_file_in_history(self, filename: str) -> int:
        """将对话历史中除最后一次之外、所有包含指定文件内容的消息折叠。

        通过 _meta 中记录的原始文件内容精确定位并替换，无需正则匹配。
        返回折叠的消息条数。
        """
        placeholder = f'[Collapse file contents: {filename}]'
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