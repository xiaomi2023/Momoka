import time

import config
from script.logger import log, user_log, new_log
from config import get_config
from script import bot
from script.system import get_cwd

TITLE = r"""
.___  ___.   ______   .___  ___.   ______   ___ ___       ___      
|   \/   |  /  __  \  |   \/   |  /  __  \  | |/  /      /   \     
|  \  /  | |  |  |  | |  \  /  | |  |  |  | |    /      /  ^  \    
|  |\/|  | |  |  |  | |  |\/|  | |  |  |  | |    \     /  /_\  \   
|  |  |  | |  `--'  | |  |  |  | |  `--'  | |     \   /  _____  \  
|__|  |__|  \______/  |__|  |__|  \______/  |__|\__\ /__/     \__\ 
"""
LINE = '-' * 20


def multiline_input(prompt: str) -> str:
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


def _build_system_prompt() -> str:
    import sys as _sys
    cfg = get_config()
    if _sys.platform == 'win32':
        platform_hint = f'Windows（{_sys.platform}）'
    elif _sys.platform == 'darwin':
        platform_hint = f'macOS（{_sys.platform}）'
    else:
        platform_hint = f'Linux（{_sys.platform}）'
    return (
        f"你是 Momoka，一个工作助理。你需要通过调用工具来操作用户的电脑并完成需求。\n"
        f"当前目录: {get_cwd()}\n"
        f"工作目录（基准）: {cfg['work_dir']}\n"
        f"操作系统: {platform_hint}\n"
        f"用{config.get_config()['language']}与用户沟通\n"
        "规则: \n" +
        (f"- 称呼用户为\"{get_config()['user_call']}\"。\n" if get_config()['user_call'] is not None else "") +
        "- 优先在工作目录中进行操作；如需操作工作目录之外的文件，请先通过 ask_user 征得同意。\n"
        "- 工作时告知你正在做或做了什么以及为什么这样做。\n"
        "- 完成所有工作后，调用 finish 交付成果。\n"
        f"{("\n" + get_config()['prompt'])
        if (get_config()['prompt'] is not None) and (get_config()['prompt'] != "") else ""}"
    )


def _agent_loop(work_bot, response, file_contents: dict,
                input_tokens: int, output_tokens: int, round_count: int) -> tuple[bool, dict, int, int, int]:
    """执行工具调用循环，直到 finish 或 Bot 返回纯文本（等待用户输入）。"""
    while True:
        text_content: str = response['content']
        tool_calls: list = response['tool_calls']

        # ── 情形A：有工具调用 ──────────────────────────────────────────
        if tool_calls:
            if text_content:
                user_log(text_content, role='BOT')

            # 记录本轮工具调用前已有的文件名，供稍后折叠使用
            prev_file_contents = dict(file_contents)

            is_finish, file_contents = tool.execute_tool_calls(work_bot, tool_calls)
            if is_finish:
                log('work DONE')
                return True, file_contents, input_tokens, output_tokens, round_count

            response = work_bot.resume(use_tools=True)
            input_tokens += response.get('input_tokens', 0)
            output_tokens += response.get('output_tokens', 0)
            round_count += 1

            # resume() 已将新 assistant 消息写入历史，此时折叠才能看到 >= 2 条记录
            # 折叠范围：本轮读到的文件（file_contents）+ 上轮已有的文件（prev_file_contents）
            cfg = get_config()
            if cfg.get('fold', True):
                to_fold = {**prev_file_contents, **file_contents}
                for filename in to_fold:
                    count = work_bot.collapse_file_in_history(filename)
                    if count:
                        log(f'折叠: {filename}（折叠了 {count} 条旧记录）')

            continue

        # ── 情形B：纯文本，交还控制权给用户 ───────────────────────────
        if text_content:
            user_log(text_content, role='BOT')
        return False, file_contents, input_tokens, output_tokens, round_count
if __name__ == '__main__':
    print(TITLE + '\n' + LINE + ' 欢迎回来！这里是 Momoka v0.1 ' + LINE)
    new_log()
    log('start')

    work_bot = bot.Bot(bot_name='Momoka')
    work_bot.set_system(_build_system_prompt())

    file_contents: dict[str, str] = {}
    start_time = time.time()
    input_tokens = 0
    output_tokens = 0
    round_count = 0

    while True:
        user_message = multiline_input('>> ')

        if user_message.strip() == '/end':
            elapsed = time.time() - start_time
            mins = int(elapsed // 60)
            secs = int(elapsed % 60)
            time_str = f'{mins}min {secs}s' if mins else f'{secs}s'
            print("-" * 67)
            print(f'结束 ({time_str} | 输入: {input_tokens} tokens | 输出: {output_tokens} tokens | {round_count}R)')
            log('end')
            break

        log(f'user: {user_message}')

        response = work_bot.message(
            user_message,
            role='user',
            file_contents=file_contents,
            use_tools=True,
        )
        input_tokens += response.get('input_tokens', 0)
        output_tokens += response.get('output_tokens', 0)
        round_count += 1

        is_finish, file_contents, input_tokens, output_tokens, round_count = _agent_loop(
            work_bot, response, file_contents, input_tokens, output_tokens, round_count
        )

        if is_finish:
            user_log('就绪')