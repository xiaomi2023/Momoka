"""
user/cli.py —— CLI 用户交互实现。

实现 BaseUser 抽象接口，处理终端的输入输出。
仅支持交互式终端（TTY）。
Spinner 动画也定义在这里，属于交互层逻辑。
"""

import sys
import threading
import time

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.status import Status
from rich.text import Text
from rich.theme import Theme

from logger import log, new_log
from user.user import BaseUser
from user.cli.util import handle_slash, multiline_input

_spinner_console = Console(highlight=False)

# Markdown 渲染用的自定义主题
_MARKDOWN_THEME = Theme({
    "markdown.text": "bright_white",
    "markdown.h1": "bright_white bold underline",
    "markdown.h2": "white bold underline",
    "markdown.h3": "bold",
    "markdown.h4": "bold",
    "markdown.h5": "bold",
    "markdown.h6": "dim italic",
    "markdown.code": "green",
    "markdown.code_block": "green",
    "markdown.block_quote": "dim italic",
    "markdown.list_item": "cyan",
    "markdown.strong": "plum1",
    "markdown.emph": "italic",
    "markdown.link": "blue underline",
    "markdown.hr": "dim",
})

# Markdown 渲染专用 Console
_console_md = Console(theme=_MARKDOWN_THEME, highlight=False)

# role → rich 颜色映射
_ROLE_COLORS: dict[str, str] = {
    'BROWSER':  'light_steel_blue',
    'MCP':      'light_steel_blue',
    'LOG':      'bright_cyan',
    'SHELL':    'bright_green',
    'WARN':     'bright_yellow',
    'ERROR':    'bright_red',
    'SETTINGS': 'bright_yellow',
    'TOOL':     'bright_cyan',
    'QUESTION': 'bright_cyan',
    'OTHERS':   'bright_cyan',
}

TITLE = r"""
.___  ___.   ______   .___  ___.   ______   ___ ___       ___      
|   \/   |  /  __  \  |   \/   |  /  __  \  | |/  /      /   \     
|  \  /  | |  |  |  | |  \  /  | |  |  |  | |    /      /  ^  \    
|  |\/|  | |  |  |  | |  |\/|  | |  |  |  | |    \     /  /_\  \   
|  |  |  | |  `--'  | |  |  |  | |  `--'  | |     \   /  _____  \  
|__|  |__|  \______/  |__|  |__|  \______/  |__|\__\ /__/     \__\ 
"""
INFO = " " * 7 + 'Developed by Mikoris | For more help, type /help'


class Spinner:
    """在 API 请求期间显示等待动画（Rich Status + ESC 中断，跨平台）。"""

    _MSG_NORMAL       = '[dim]Press ESC to Interrupt[/dim]'
    _MSG_INTERRUPTING = '[red]Interrupting...[/red][dim](Press Ctrl+C to force stop)[/dim]'

    def __init__(self):
        self._stop        = threading.Event()
        self._interrupted = threading.Event()
        self._input_thread: threading.Thread | None = None
        self._status: Status | None = None

    def _check_input_windows(self):
        """Windows 平台：使用 msvcrt 检测按键。"""
        try:
            import msvcrt
            while not self._stop.is_set():
                if msvcrt.kbhit():
                    key = msvcrt.getch()
                    if key == b'\x1b':  # ESC
                        self._interrupted.set()
                        if self._status is not None:
                            self._status.update(self._MSG_INTERRUPTING)
                        while msvcrt.kbhit():
                            msvcrt.getch()
                        break
                time.sleep(0.05)
        except Exception:
            pass

    def _check_input_unix(self):
        """Unix/Linux/Mac 平台：使用 termios 和 select 检测按键。"""
        import select
        import termios
        import tty

        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)
        try:
            tty.setraw(fd)
            while not self._stop.is_set():
                ready, _, _ = select.select([sys.stdin], [], [], 0.05)
                if ready:
                    key = sys.stdin.read(1)
                    if key == '\x1b':
                        self._interrupted.set()
                        if self._status is not None:
                            self._status.update(self._MSG_INTERRUPTING)
                        break
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)

    def _check_input(self):
        """根据平台选择合适的中断检测方法。"""
        try:
            if sys.platform == 'win32':
                self._check_input_windows()
            else:
                self._check_input_unix()
        except Exception:
            pass

    def __enter__(self):
        self._status = _spinner_console.status(
            self._MSG_NORMAL,
            spinner='dots',
            spinner_style='cyan',
        )
        self._status.__enter__()
        self._input_thread = threading.Thread(target=self._check_input, daemon=True)
        self._input_thread.start()
        return self

    def __exit__(self, *_):
        self._stop.set()
        if self._status is not None:
            self._status.__exit__(None, None, None)
            self._status = None
        if self._input_thread:
            self._input_thread.join(timeout=0.1)

    def is_interrupted(self) -> bool:
        return self._interrupted.is_set()


class CLIUser(BaseUser):
    """基于交互式终端的用户交互实现。"""
    
    interface_type = 'cli'

    def __init__(self):
        super().__init__()
        self._agent = None
        self._start_time = 0.0
        self._console = Console(highlight=False)

    def set_agent(self, agent):
        """设置关联的 Agent 实例。"""
        self._agent = agent

    def __show_welcome(self) -> None:
        """显示欢迎界面。"""
        _con = Console(highlight=False)
        _footer = "\n" + " " * 19 + 'Welcome back! This is Momoka~\n'
        pink_title = Text(TITLE.strip(), style='plum1')
        _con.print(Panel(
            pink_title + '\n' + _footer,
            border_style='bright_cyan', padding=(0, 2), expand=False,
            subtitle=INFO.strip(), subtitle_align='center',
        ))

    def run(self) -> None:
        """启动交互式会话循环。"""
        if self._agent is None:
            raise RuntimeError("Agent not set. Call set_agent() before run().")

        # 非交互式终端警告
        if not sys.stdout.isatty():
            _console = Console(highlight=False, stderr=True)
            _console.print(
                '[bright_yellow]⚠ WARNING:[/bright_yellow] Non-interactive terminal detected.\n'
                '  CLI mode is designed for [bold]interactive terminals[/bold] only.\n'
                f'  Consider using [bold cyan]--headless stdio[/bold cyan] for pipe/redirect/file scenarios.\n'
            )

        new_log()
        log('start')

        self.__show_welcome()

        self._start_time = time.time()
        self.session.reset()

        while True:
            print()
            user_message = self.get_input()
            self._console.rule(style='bright_black')

            if user_message.strip() == '/end':
                self.on_session_end(
                    self.session.input_tokens,
                    self.session.output_tokens,
                    self.session.round_count,
                    time.time() - self._start_time
                )
                log('end')
                break

            handled, skill_name = handle_slash(
                user_message,
                self.session.input_tokens,
                self.session.output_tokens,
                self.session.round_count,
                self._start_time
            )

            if handled and skill_name is None:
                continue

            # Repair orphaned tool_calls messages in history
            repaired = self._agent.repair_history()
            if repaired:
                log(f'main | repair_history: filled in {repaired} orphaned tool_results')

            if handled and skill_name is not None:
                if skill_name == '__init__':
                    self._handle_init_command()
                    continue

                if skill_name == '__clear_ask__':
                    self._handle_clear_command()
                    continue

                # /skill_name 强制加载 skill
                log(f'skill trigger: {skill_name}')
                load_result = self._agent.load_skill(skill_name)
                if load_result.success:
                    Console().print(f'[bright_cyan]Load Skill: {skill_name}[/bright_cyan]')
                    log(f'system (skill inject): {skill_name}')
                else:
                    Console().print(f'[bright_red]Non-existent command or skill: {skill_name}[/bright_red]')
                continue

            # 普通用户消息，交给 agent 处理
            result = self._agent.send(user_message)

            self.session.update(result)

            self._console.rule(style='bright_black')

            if result.is_finish:
                self._agent.finish_task()

    def get_input(self) -> str:
        return multiline_input('>> ')

    def send_output(self, message: str, role: str = 'BOT') -> None:
        self.user_log(message, role=role)

    def send_error(self, message: str) -> None:
        self.user_log(message, role='ERROR')

    def user_log(self, message: str, end: str = '\n', role: str = 'LOG',
                 panel: bool = False, panel_title: str | None = None) -> None:
        """CLI 实现：带 Rich 染色和 mute_log 过滤。"""
        from config import get_config

        if role in get_config().get('mute_log', []):
            return

        if role == 'BOT':
            md = Markdown(message)
            _console_md.print(md, end=end)
            return

        if panel:
            title = panel_title if panel_title is not None else role
            color = _ROLE_COLORS.get(role, _ROLE_COLORS['OTHERS'])
            p = Panel(message, title=title, border_style=color, title_align='left')
            self._console.print(p, end=end)
            return

        color = _ROLE_COLORS.get(role, _ROLE_COLORS['OTHERS'])
        prefix = ' • '
        t = Text(prefix, style='plum1') + Text(message, style=color)
        self._console.print(t, end=end)

    def _handle_init_command(self) -> None:
        """处理 /init 命令，委托 Agent 层生成 AGENTS.md 文件。"""
        console = Console()

        console.print('[bright_cyan]Generating AGENTS.md...[/bright_cyan]')

        try:
            success = self._agent.initialize_project()

            if success:
                console.print('[bright_green]AGENTS.md generated successfully[/bright_green]')
            else:
                console.print('[bright_red]Failed to generate AGENTS.md[/bright_red]')

        except Exception as e:
            console.print(f'[bright_red]Failed to generate AGENTS.md: {e}[/bright_red]')

    def _handle_clear_command(self) -> None:
        """处理 /clear 命令，清空对话历史并重置会话状态（带确认提示）。"""
        from rich.prompt import Confirm

        console = Console()

        try:
            confirmed = Confirm.ask(
                '[bright_yellow]Are you sure you want to clear the conversation history?[/bright_yellow]'
            )

            if not confirmed:
                console.print('[dim]Cancelled.[/dim]')
                return

            self._agent.clear_context()
            self.session.reset()
            self.on_clear_context()

            console.print('[bright_cyan]Context cleared.[/bright_cyan]')

        except Exception as e:
            console.print(f'[bright_red]Failed to clear context: \n{e}[/bright_red]')

    def on_session_end(self, input_tokens: int, output_tokens: int,
                       round_count: int, elapsed: float) -> None:
        mins = int(elapsed // 60)
        secs = int(elapsed % 60)
        time_str = f'{mins}min {secs}s' if mins else f'{secs}s'
        print(f'Done ({time_str} | Input: {input_tokens} tokens | Output: {output_tokens} tokens | {round_count}R)')

    def call_wrapper(self, fn, *args, **kwargs):
        """在 spinner 动画中执行函数调用，支持 ESC 中断。"""
        spinner = Spinner()
        with spinner:
            result = fn(*args, **kwargs)
            if spinner.is_interrupted():
                self._pending_interrupt = True
        return result

    @property
    def pending_interrupt(self) -> bool:
        """是否有待处理的中断请求。读取后自动清除。"""
        flag = getattr(self, '_pending_interrupt', False)
        self._pending_interrupt = False
        return flag
