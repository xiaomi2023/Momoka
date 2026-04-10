"""
user/cli/util.py —— 终端交互工具函数。

包含多行输入、slash 命令处理等与主循环交互相关的工具函数。
"""

import json
import re
import time

from config import get_config


from rich.text import Text

SLASH_HELP = (
    "[bright_cyan]  /end                — End session and show usage statistics\n"
    "  /usage              — Show current token usage\n"
    "  /config             — Show config\n"
    "  /working_config     — Show working_config\n"
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
    """支持行尾 \\ 续行的多行输入。"""
    lines = []
    first = True
    while True:
        line = input(prompt if first else '... ')
        first = False
        if line.endswith('\\'):
            lines.append(line[:-1])
        else:
            lines.append(line)
            break
    return '\n'.join(lines)


def fetch_available_models(console=None) -> list[str]:
    """从 API 拉取所有可用模型列表，返回 model id 字符串列表。

    失败时返回空列表并打印错误信息。
    如果提供 console 参数，则使用 rich 进度条显示加载状态。
    """
    try:
        from openai import OpenAI
        cfg = get_config()
        client = OpenAI(api_key=cfg['api_key'], base_url=cfg['base_url'])
        
        if console is not None:
            from rich.progress import Progress, SpinnerColumn, TextColumn
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console,
                transient=True,
            ) as progress:
                task = progress.add_task("Fetching available models...", total=None)
                models = client.models.list()
                progress.stop()
        else:
            models = client.models.list()
        
        ids = sorted(m.id for m in models.data)
        return ids
    except Exception as e:
        from rich.console import Console
        Console().print(f'[bright_red]Failed to fetch models: {e}[/bright_red]')
        return []


def select_model_interactive(models: list[str], current: str) -> tuple[str | None, int]:
    """用上下方向键让用户从 models 列表中选择一个模型。

    Returns:
        (选中的 model id, 列表行数)；用户按 ESC/q 取消时返回 (None, 列表行数)。
        列表行数用于后续清屏。
    """
    import sys

    if not models:
        return None, 0

    # 初始光标位置：优先定位到当前模型
    try:
        idx = models.index(current)
    except ValueError:
        idx = 0

    # 计算列表总行数：标题1行 + 模型列表行数 + 末尾空行1行
    list_lines = 1 + len(models) + 1

    def _render(selected_idx: int) -> None:
        # 清屏已打印的行并重绘
        sys.stdout.write(f'\x1b[{list_lines}A\r')  # 上移
        _print_list(selected_idx)

    def _print_list(selected_idx: int) -> None:
        print('\x1b[1;96m  Select model (↑↓ to move, Enter to confirm, ESC/q to cancel):\x1b[0m')
        for i, m in enumerate(models):
            marker = '▶ ' if i == selected_idx else '  '
            active = ' [current]' if m == current else ''
            line = f'  {marker}{m}{active}'
            if i == selected_idx:
                # 高亮选中行（粗体 + 青色）
                print(f'\x1b[1;36m{line}\x1b[0m')
            else:
                print(line)
        print()  # 末尾空行，使上移计算正确

    if sys.platform == 'win32':
        result = _select_model_windows(models, current, idx, _print_list, _render)
    else:
        result = _select_model_unix(models, current, idx, _print_list, _render)
    
    return result, list_lines


def _select_model_windows(models, current, idx, print_list_fn, render_fn):
    """Windows 平台：用 msvcrt 读取方向键。"""
    import msvcrt
    print_list_fn(idx)
    while True:
        key = msvcrt.getch()
        if key in (b'\x00', b'\xe0'):          # 特殊键前缀
            key2 = msvcrt.getch()
            if key2 == b'H':                   # 上
                idx = (idx - 1) % len(models)
                render_fn(idx)
            elif key2 == b'P':                 # 下
                idx = (idx + 1) % len(models)
                render_fn(idx)
        elif key == b'\r':                     # Enter
            return models[idx]
        elif key in (b'\x1b', b'q', b'Q'):    # ESC / q
            return None


def _select_model_unix(models, current, idx, print_list_fn, render_fn):
    """Unix 平台：用 termios + tty 原始模式读取方向键。"""
    import sys
    import termios
    import tty

    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    print_list_fn(idx)
    try:
        tty.setraw(fd)
        while True:
            ch = sys.stdin.read(1)
            if ch == '\x1b':
                ch2 = sys.stdin.read(1)
                if ch2 == '[':
                    ch3 = sys.stdin.read(1)
                    if ch3 == 'A':             # ↑
                        idx = (idx - 1) % len(models)
                        render_fn(idx)
                    elif ch3 == 'B':           # ↓
                        idx = (idx + 1) % len(models)
                        render_fn(idx)
                else:
                    # 裸 ESC
                    return None
            elif ch in ('\r', '\n'):           # Enter
                return models[idx]
            elif ch in ('q', 'Q'):
                return None
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)


def handle_slash(cmd: str, input_tokens: int, output_tokens: int,
                 round_count: int, start_time: float) -> tuple[bool, str | None]:
    """处理 / 开头的内置命令。

    Returns:
        (handled, skill_name)
        handled:    True 表示已处理（主循环应 continue 或走 skill 分支）
        skill_name: 非 None 时表示需要强制触发该技能
    """
    cmd = cmd.strip()

    if cmd == '/usage':
        elapsed = time.time() - start_time
        mins = int(elapsed // 60)
        secs = int(elapsed % 60)
        time_str = f'{mins}min {secs}s' if mins else f'{secs}s'
        from rich.console import Console
        Console().print(f'[bright_cyan]Usage: Input {input_tokens} tokens | Output {output_tokens} tokens | '
              f'{round_count}R | Time taken {time_str}[/bright_cyan]')
        return True, None

    if cmd == '/config':
        try:
            cfg = get_config()
            display = {k: ('***' if 'key' in k.lower() else v) for k, v in cfg.items()}
            from rich.console import Console
            Console().print(f'[bright_cyan]{json.dumps(display, ensure_ascii=False, indent=2)}[/bright_cyan]')
        except Exception as e:
            from rich.console import Console
            Console().print(f'[bright_red]Failed in reading config: {e}[/bright_red]')
        return True, None

    if cmd == '/working_config':
        try:
            from config import get_working_config
            wc = get_working_config()
            from rich.console import Console
            Console().print(f'[bright_cyan]{json.dumps(wc, ensure_ascii=False, indent=2)}[/bright_cyan]')
        except Exception as e:
            from rich.console import Console
            Console().print(f'[bright_red]Failed in reading working_config: {e}[/bright_red]')
        return True, None

    if cmd == '/help':
        from rich.console import Console
        Console().print(SLASH_HELP)
        return True, None

    if cmd == '/model':
        _handle_model_command()
        return True, None

    if cmd == '/set' or cmd.startswith('/set '):
        parts = cmd[5:].strip().split(None, 1)
        if len(parts) != 2:
            from rich.console import Console
            console = Console()
            # 显示可用的配置项及其说明
            config_help = """[bright_cyan]Available configuration options:

  api_key    — LLM API key for authentication
  base_url   — API base URL endpoint
  model      — Model name to use (e.g., gpt-4o)
  work_dir   — Default working directory path
  encoding   — File encoding (default: utf-8)
  fold       — Fold history file content in output (true/false)
  mute_log   — List of roles to mute in logs (e.g., ["SHELL", "BROWSER"])
  prompt     — Additional system prompt text

Usage: /set <key> <value>[/bright_cyan]"""
            console.print(config_help)
            return True, None
        key, raw_value = parts
        try:
            from config import CONFIG_FILE
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                cfg = json.load(f)
        except Exception as e:
            from rich.console import Console
            Console().print(f'[bright_red]Failed to read config: {e}[/bright_red]')
            return True, None
        if key not in cfg:
            allowed = ', '.join(sorted(cfg.keys()))
            from rich.console import Console
            Console().print(f'[bright_red]Unknown config key: {key}\nAllowed keys: {allowed}[/bright_red]')
            return True, None
        value = _infer_type(raw_value)
        cfg[key] = value
        try:
            with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
                json.dump(cfg, f, ensure_ascii=False, indent=2)
        except Exception as e:
            from rich.console import Console
            Console().print(f'[bright_red]Failed to write config: {e}[/bright_red]')
            return True, None
        display_value = '***' if 'key' in key.lower() else repr(value)
        from rich.console import Console
        Console().print(f'[bright_cyan]config updated: {key} = {display_value}[/bright_cyan]')
        return True, None

    if cmd == '/init':
        # 返回特殊标记，让主循环处理
        return True, '__init__'

    # ── /skill_name 强制调用技能 ────────────────────────────────────────
    m = re.fullmatch(r'/([\w\-]+)', cmd)
    if m:
        return True, m.group(1).strip()
    if cmd.startswith('/'):
        from rich.console import Console
        Console().print(f'[bright_red]Unknown command: {cmd}[/bright_red]')
        return True, None

    return False, None


def _handle_model_command() -> None:
    """执行 /model 命令的完整流程：拉取列表 → 交互选择 → 写入配置。"""
    import sys
    from rich.console import Console

    # 非 TTY 环境（如管道）降级为纯文本输入
    if not sys.stdout.isatty():
        _handle_model_fallback()
        return

    console = Console(highlight=False)
    models = fetch_available_models(console=console)
    if not models:
        console.print('[bright_red]No models available or failed to fetch.[/bright_red]\n')
        return

    cfg = get_config()
    current = cfg.get('model', '')

    chosen, list_lines = select_model_interactive(models, current)

    # 清除选择界面：上移并清空所有行
    if list_lines > 0:
        sys.stdout.write(f'\x1b[{list_lines}A\r')
        for _ in range(list_lines):
            sys.stdout.write('\x1b[K\n')
        sys.stdout.write(f'\x1b[{list_lines}A\r')

    if chosen is None:
        console.print('[dim]Cancelled.[/dim]\n')
        return

    if chosen == current:
        console.print(f'[dim]Model unchanged: {chosen}[/dim]\n')
        return

    # 写入 config.json
    try:
        from config import CONFIG_FILE
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            raw = json.load(f)
        raw['model'] = chosen
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(raw, f, ensure_ascii=False, indent=2)
        console.print(f'[bright_cyan]Model updated: {current!r} → {chosen!r}[/bright_cyan]\n')
    except Exception as e:
        console.print(f'[bright_red]Failed to save model: {e}[/bright_red]\n')


def _handle_model_fallback() -> None:
    """非 TTY 环境下的 /model 降级实现：打印列表，手动输入序号。"""
    from rich.console import Console
    Console().print('[bright_cyan]Fetching available models...[/bright_cyan]')
    models = fetch_available_models()
    if not models:
        Console().print('[bright_cyan]No models available or failed to fetch.[/bright_cyan]')
        return

    cfg = get_config()
    current = cfg.get('model', '')

    from rich.console import Console
    Console().print('[bright_cyan]\nModels:[/bright_cyan]')
    for i, m in enumerate(models):
        active = ' [current]' if m == current else ''
        Console().print(f'[cyan]  {i + 1:>3}. {m}{active}[/cyan]')

    try:
        raw = input(f'Enter number (1-{len(models)}) or leave blank to cancel: ').strip()
    except (EOFError, KeyboardInterrupt):
        from rich.console import Console
        Console().print('[bright_cyan]\nCancelled.[/bright_cyan]')
        return

    if not raw:
        from rich.console import Console
        Console().print('[bright_cyan]Cancelled.[/bright_cyan]')
        return

    try:
        n = int(raw)
        if not (1 <= n <= len(models)):
            raise ValueError
    except ValueError:
        from rich.console import Console
        Console().print(f'[bright_red]Invalid input: {raw!r}[/bright_red]')
        return

    chosen = models[n - 1]
    if chosen == current:
        from rich.console import Console
        Console().print(f'[bright_cyan]Model unchanged: {chosen}[/bright_cyan]')
        return

    try:
        from config import CONFIG_FILE
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            raw_cfg = json.load(f)
        raw_cfg['model'] = chosen
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(raw_cfg, f, ensure_ascii=False, indent=2)
        from rich.console import Console
        Console().print(f'[bright_cyan]Model updated: {current!r} → {chosen!r}[/bright_cyan]')
    except Exception as e:
        from rich.console import Console
        Console().print(f'[bright_red]Failed to save model: {e}[/bright_red]')