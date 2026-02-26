import logging

# ── 主日志（系统事件、指令解析等）────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(message)s',
    filename='log.txt',
    filemode='a',
    encoding='utf-8'
)

# ── 对话历史专用日志 ────────────────────────────────────────────────
_chat_logger = logging.getLogger('chat_history')
_chat_logger.setLevel(logging.INFO)
_chat_logger.propagate = False  # 不传播到根 logger，避免混入 log.txt

_chat_handler = logging.FileHandler('chat_history_log.txt', mode='a', encoding='utf-8')
_chat_handler.setFormatter(logging.Formatter('[%(asctime)s] %(message)s'))
_chat_logger.addHandler(_chat_handler)


def log(message: str) -> None:
    logging.info(message)


def chat_log(message: str) -> None:
    """记录 Bot 对话历史到 chat_history_log.txt。"""
    _chat_logger.info(message)


def new_log():
    """清空 log.txt 和 chat_history_log.txt。"""
    with open('log.txt', 'w'):
        pass
    with open('chat_history_log.txt', 'w'):
        pass


def user_log(message: str, end='\n', role='LOG') -> None:
    from config import get_config
    if role in get_config().get('mute_log', []):
        return
    print(f'[{role}] ' + message, end=end)