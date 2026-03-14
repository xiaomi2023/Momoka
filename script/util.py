"""
util.py —— 终端交互工具函数。

包含多行输入、slash 命令处理等与主循环交互相关的工具函数。
"""

import json
import re
import time

from config import get_config


SLASH_HELP = (
    "  /end            — 结束会话并显示用量统计\n"
    "  /usage          — 显示当前 token 用量\n"
    "  /config         — 显示 config.json 配置\n"
    "  /working_config — 显示 working_config 配置\n"
    "  /skill_name     — 加载并执行指定skill\n"
    "  /help           — 显示帮助\n"
)


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
        print(f'用量: 输入 {input_tokens} tokens | 输出 {output_tokens} tokens | '
              f'{round_count}R | 已用时 {time_str}\n')
        return True, None

    if cmd == '/config':
        try:
            cfg = get_config()
            display = {k: ('***' if 'key' in k.lower() else v) for k, v in cfg.items()}
            print(json.dumps(display, ensure_ascii=False, indent=2), end='\n\n')
        except Exception as e:
            print(f'读取 config 失败: {e}\n')
        return True, None

    if cmd == '/working_config':
        try:
            from config import get_working_config
            wc = get_working_config()
            print(json.dumps(wc, ensure_ascii=False, indent=2), end='\n\n')
        except Exception as e:
            print(f'读取 working_config 失败: {e}\n')
        return True, None

    if cmd == '/help':
        print(SLASH_HELP)
        return True, None


    # ── /skill_name 强制调用技能（内置命令兜底后）──────────────────────
    m = re.fullmatch(r'/([\w\-]+)', cmd)
    if m:
        return True, m.group(1).strip()
    if cmd.startswith('/'):
        print(f'未知命令: {cmd}\n')
        return True, None

    return False, None