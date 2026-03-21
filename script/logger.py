import logging
import os

_BASE = os.path.dirname(os.path.abspath(__file__))   # script/ 目录
_LOG_DIR = os.path.join(_BASE, '..', 'logs')         # Momoka/logs/
os.makedirs(_LOG_DIR, exist_ok=True)

_LOG_FILE      = os.path.join(_LOG_DIR, 'log.txt')
_CHAT_LOG_FILE = os.path.join(_LOG_DIR, 'chat_history_log.txt')

# ── 主日志（系统事件、指令解析等）────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(message)s',
    filename=_LOG_FILE,
    filemode='a',
    encoding='utf-8'
)

# ── 对话历史专用日志 ────────────────────────────────────────────────
_chat_logger = logging.getLogger('chat_history')
_chat_logger.setLevel(logging.INFO)
_chat_logger.propagate = False  # 不传播到根 logger，避免混入 log.txt

_chat_handler = logging.FileHandler(_CHAT_LOG_FILE, mode='a', encoding='utf-8')
_chat_handler.setFormatter(logging.Formatter('[%(asctime)s] %(message)s'))
_chat_logger.addHandler(_chat_handler)

# ── Rich 染色支持（可选依赖）────────────────────────────────────────
try:
    from rich.console import Console
    from rich.text import Text
    _rich_console = Console(highlight=False)
    _rich_available = True
    _supports_color = _rich_console.color_system is not None
except ImportError:
    import warnings
    warnings.warn(
        'rich is not installed. Run: \npip install rich \nto use full logging functionality.',
        ImportWarning,
        stacklevel=2,
    )
    _rich_console = None
    _rich_available = False
    _supports_color = False

# role → rich 颜色映射（BOT 不染色）
_ROLE_COLORS: dict[str, str] = {
    'BROWSER':  'bright_magenta',
    'LOG':      'bright_cyan',
    'SHELL':    'bright_green',
    'WARN':     'bright_yellow',
    'ERROR':    'red',
    'SETTINGS': 'bright_yellow',
}


def log(message: str) -> None:
    logging.info(message)


def chat_log(message: str) -> None:
    """记录 Bot 对话历史到 chat_history_log.txt。"""
    _chat_logger.info(message)


def new_log():
    """清空 log.txt 和 chat_history_log.txt。"""
    with open(_LOG_FILE, 'w'):
        pass
    with open(_CHAT_LOG_FILE, 'w'):
        pass


def user_log(message: str, end='\n', role='LOG') -> None:
    from config import get_config
    if role in get_config().get('mute_log', []):
        return

    show_prefix = not _supports_color
    prefix = f'[{role}] ' if (show_prefix and role != 'BOT') else ''
    full_text = prefix + message

    if _rich_available and role in _ROLE_COLORS:
        color = _ROLE_COLORS[role]
        t = Text(full_text, style=color)
        _rich_console.print(t, end=end)
    else:
        print(full_text, end=end)