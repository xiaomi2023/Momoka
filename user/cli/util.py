"""
user/cli/util.py —— CLI 交互式终端工具函数。

包含多行输入、slash 命令处理等与主循环交互相关的工具函数。
仅支持交互式终端（TTY）。
"""

import json
import re
import sys
import time

from rich.console import Console
from rich.text import Text

from config import get_config

SLASH_HELP = (
    "[bright_cyan]  /end                — End session and show usage statistics\n"
    "  /usage              — Show current token usage\n"
    "  /clear              — Clear conversation history\n"
    "  /config             — Show config\n"
    "  /working_config     — Show runtime config (memory)\n"
    "  /set <key> <value>  — Modify configuration in config\n"
    "  /model              — Select and switch the current model\n"
    "  /skill_name         — Load specified skill\n"
    "  /init               — Generate AGENTS.md for current project\n"
    "  /help               — Show help[/bright_cyan]\n"
)


def _infer_type(s: str) -> bool | int | float | str:
    """将字符串 value 推断为合适的 Python 类型。"""
    if s.lower() == 'true':
        return True
    if s.lower() == 'false':
        return False
    try:
        return int(s)
    except ValueError:
        pass
    try:
        return float(s)
    except ValueError:
        pass
    return s


def multiline_input(prompt: str) -> str:
    """使用 prompt_toolkit 实现多行输入，仅支持交互式终端。

    - Enter 提交输入
    - Windows: Ctrl+J 换行
    - Unix/Linux/Mac: Shift+Enter 换行

    配备语法历史记录，超长输入自动换行显示。
    """
    from prompt_toolkit import PromptSession
    from prompt_toolkit.history import InMemoryHistory
    from prompt_toolkit.key_binding import KeyBindings, KeyPressEvent

    if not hasattr(multiline_input, '_session'):
        try:
            bindings = KeyBindings()

            @bindings.add('enter')
            def _accept(event: KeyPressEvent) -> None:
                """Enter → 提交当前输入。"""
                buf = event.current_buffer
                if buf.text:
                    buf.validate_and_handle()

            if sys.platform == 'win32':
                @bindings.add('c-j')
                def _newline_windows(event: KeyPressEvent) -> None:
                    """Ctrl+J → 插入换行（Windows）。"""
                    event.current_buffer.insert_text('\n')
            else:
                try:
                    @bindings.add('s-return')
                    def _newline_unix(event: KeyPressEvent) -> None:
                        """Shift+Enter → 插入换行（Unix/Linux/Mac）。"""
                        event.current_buffer.insert_text('\n')
                except ValueError:
                    try:
                        @bindings.add('s-enter')
                        def _newline_unix_legacy(event: KeyPressEvent) -> None:
                            """Shift+Enter → 插入换行（旧版 prompt_toolkit 兼容）。"""
                            event.current_buffer.insert_text('\n')
                    except ValueError:
                        @bindings.add('escape', 'enter')
                        def _newline_fallback(event: KeyPressEvent) -> None:
                            """Alt+Enter → 插入换行（降级方案）。"""
                            event.current_buffer.insert_text('\n')

            multiline_input._session = PromptSession(
                history=InMemoryHistory(),
                key_bindings=bindings,
                multiline=False,
                prompt_continuation='.. ',
            )
        except Exception:
            # prompt_toolkit 初始化失败时降级
            return _multiline_input_fallback(prompt)

    try:
        return multiline_input._session.prompt(prompt).strip()
    except (EOFError, KeyboardInterrupt):
        return ''


def _multiline_input_fallback(prompt: str) -> str:
    """降级方案：使用基础 input()，以 \\ 结尾表示换行继续输入。"""
    lines = []
    while True:
        try:
            line = input(prompt)
        except (EOFError, KeyboardInterrupt):
            return ''
        if line.endswith('\\'):
            lines.append(line[:-1])
            prompt = '.. '
        else:
            lines.append(line)
            break
    return '\n'.join(lines).strip()


def handle_slash(cmd: str, input_tokens: int, output_tokens: int,
                 round_count: int, start_time: float) -> tuple[bool, str | None]:
    """处理 / 开头的内置命令。

    Returns:
        (handled, skill_name)
        handled:    True 表示已处理
        skill_name: 非 None 时表示需要强制触发该技能
    """
    cmd = cmd.strip()

    if cmd == '/usage':
        elapsed = time.time() - start_time
        mins = int(elapsed // 60)
        secs = int(elapsed % 60)
        time_str = f'{mins}min {secs}s' if mins else f'{secs}s'
        Console().print(f'[bright_cyan]Usage: Input {input_tokens} tokens | Output {output_tokens} tokens | '
                        f'{round_count}R | Time taken {time_str}[/bright_cyan]')
        return True, None

    if cmd == '/clear':
        return True, '__clear_ask__'

    if cmd == '/config':
        try:
            cfg = get_config()
            display = {k: ('***' if 'key' in k.lower() else v) for k, v in cfg.items()}
            Console().print(f'[bright_cyan]{json.dumps(display, ensure_ascii=False, indent=2)}[/bright_cyan]')
        except Exception as e:
            Console().print(f'[bright_red]Failed in reading config: {e}[/bright_red]')
        return True, None

    if cmd == '/working_config':
        try:
            from config import get_working_config
            wc = get_working_config()
            Console().print(f'[bright_cyan]{json.dumps(wc, ensure_ascii=False, indent=2)}[/bright_cyan]')
        except Exception as e:
            Console().print(f'[bright_red]Failed in reading working_config: {e}[/bright_red]')
        return True, None

    if cmd == '/help':
        Console().print(SLASH_HELP)
        return True, None

    if cmd == '/model':
        _handle_model_command()
        return True, None

    if cmd == '/set' or cmd.startswith('/set '):
        parts = cmd[5:].strip().split(None, 1)
        if len(parts) != 2:
            config_help = """[bright_cyan]Available configuration options:

  api_key    — LLM API key for authentication
  base_url   — API base URL endpoint
  model      — Model name to use (e.g., gpt-4o)
  work_dir   — Default working directory path
  encoding   — File encoding (default: utf-8)
  mute_log   — List of roles to mute in logs (e.g., ["SHELL", "BROWSER"])
  prompt     — Additional system prompt text

Usage: /set <key> <value>[/bright_cyan]"""
            Console().print(config_help)
            return True, None
        key, raw_value = parts
        try:
            from config import CONFIG_FILE
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                cfg = json.load(f)
        except Exception as e:
            Console().print(f'[bright_red]Failed to read config: {e}[/bright_red]')
            return True, None
        if key not in cfg:
            allowed = ', '.join(sorted(cfg.keys()))
            Console().print(f'[bright_red]Unknown config key: {key}\nAllowed keys: {allowed}[/bright_red]')
            return True, None
        value = _infer_type(raw_value)
        cfg[key] = value
        try:
            with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
                json.dump(cfg, f, ensure_ascii=False, indent=2)
        except Exception as e:
            Console().print(f'[bright_red]Failed to write config: {e}[/bright_red]')
            return True, None
        display_value = '***' if 'key' in key.lower() else repr(value)
        Console().print(f'[bright_cyan]config updated: {key} = {display_value}[/bright_cyan]')
        return True, None

    if cmd == '/init':
        return True, '__init__'

    # ── /skill_name 强制调用技能 ────────────────────────────────────────
    m = re.fullmatch(r'/([\w\-]+)', cmd)
    if m:
        return True, m.group(1).strip()
    if cmd.startswith('/'):
        Console().print(f'[bright_red]Unknown command: {cmd}[/bright_red]')
        return True, None

    return False, None


def _handle_model_command() -> None:
    """执行 /model 命令：拉取列表 → 交互选择 → 写入配置。"""
    from model.model import fetch_available_models as _fetch

    with console_status("Fetching available models..."):
        models = _fetch()

    if not models:
        Console().print('[bright_red]No models available or failed to fetch.[/bright_red]\n')
        return

    cfg = get_config()
    current = cfg.get('model', '')

    chosen = _select_model_dialog(models, current)

    if chosen is None:
        Console().print('[dim]Cancelled.[/dim]')
        return

    if chosen == current:
        Console().print(f'[dim]Model unchanged: {chosen}[/dim]')
        return

    try:
        from config import CONFIG_FILE
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            raw = json.load(f)
        raw['model'] = chosen
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(raw, f, ensure_ascii=False, indent=2)
        Console().print(f'[bright_cyan]Model updated: {current!r} → {chosen!r}[/bright_cyan]')
    except Exception as e:
        Console().print(f'[bright_red]Failed to save model: {e}[/bright_red]')


def console_status(text: str):
    """返回一个 Rich Status 上下文管理器。"""
    from rich.console import Console
    from rich.status import Status
    return Status(text, console=Console(highlight=False), spinner='dots', spinner_style='cyan')


def _select_model_dialog(models: list[str], current: str) -> str | None:
    """交互式模型选择对话框。使用 Rich Live 实现上下键导航。

    Returns:
        选中的 model id，取消返回 None。
    """
    from rich.live import Live
    from rich.table import Table
    from rich.style import Style

    idx = 0
    try:
        idx = models.index(current)
    except ValueError:
        pass

    result: str | None = None
    cancelled = False

    def _build_table(cursor: int) -> Table:
        table = Table(show_header=False, box=None, padding=(0, 1))
        table.add_column(style='bold cyan', width=2)   # marker
        table.add_column('model')                        # model name
        for i, m in enumerate(models):
            if i == cursor:
                table.add_row('▶', f'[bold cyan]{m}[/bold cyan]'
                             + (' [dim](current)[/dim]' if m == current else ''))
            else:
                table.add_row('  ', m + (' [dim](current)[/dim]' if m == current else ''))
        return table

    # 使用一个包含标题和表格的 Group，让 Live 管理所有内容
    # 这样退出 Live 后可以用 transient 完全清除
    from rich.console import Group

    def _build_content(cursor: int) -> Group:
        title = Text('Select model (↑↓ move, Enter confirm, ESC/q cancel):', style='bold cyan')
        return Group(title, _build_table(cursor))

    with Live(_build_content(idx), console=Console(highlight=False),
              refresh_per_second=10, auto_refresh=False,
              screen=False, vertical_overflow='visible',
              transient=True) as live:
        live.update(_build_content(idx), refresh=True)

        while True:
            key = _get_key_blocking()
            if key == '\x1b[A':  # Up
                idx = (idx - 1) % len(models)
                live.update(_build_content(idx), refresh=True)
            elif key == '\x1b[B':  # Down
                idx = (idx + 1) % len(models)
                live.update(_build_content(idx), refresh=True)
            elif key == '\r':  # Enter
                result = models[idx]
                break
            elif key in ('\x1b', 'q', 'Q'):  # ESC / q
                cancelled = True
                break

    return None if cancelled else result


def _get_key_blocking() -> str:
    """跨平台阻塞获取单个按键。"""
    if sys.platform == 'win32':
        import msvcrt
        key = msvcrt.getch()
        if key in (b'\x00', b'\xe0'):
            key2 = msvcrt.getch()
            if key2 == b'H':
                return '\x1b[A'
            elif key2 == b'P':
                return '\x1b[B'
            return ''
        if key == b'\r':
            return '\r'
        if key == b'\x1b':
            return '\x1b'
        if key in (b'q', b'Q'):
            return 'q'
        return key.decode('utf-8', errors='replace')
    else:
        import termios
        import tty
        fd = sys.stdin.fileno()
        old = termios.tcgetattr(fd)
        try:
            tty.setraw(fd)
            ch = sys.stdin.read(1)
            if ch == '\x1b':
                ch2 = sys.stdin.read(1)
                if ch2 == '[':
                    ch3 = sys.stdin.read(1)
                    if ch3 == 'A':
                        return '\x1b[A'
                    elif ch3 == 'B':
                        return '\x1b[B'
                return '\x1b'
            if ch in ('\r', '\n'):
                return '\r'
            if ch in ('q', 'Q'):
                return 'q'
            return ch
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old)
