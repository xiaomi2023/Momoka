import time

from script.logger import log, user_log, new_log
import script.tools as tools
import script.bot as bot
from script.prompt_builder import build_system_prompt
from script.util import multiline_input, handle_slash

TITLE = r"""
.___  ___.   ______   .___  ___.   ______   ___ ___       ___      
|   \/   |  /  __  \  |   \/   |  /  __  \  | |/  /      /   \     
|  \  /  | |  |  |  | |  \  /  | |  |  |  | |    /      /  ^  \    
|  |\/|  | |  |  |  | |  |\/|  | |  |  |  | |    \     /  /_\  \   
|  |  |  | |  `--'  | |  |  |  | |  `--'  | |     \   /  _____  \  
|__|  |__|  \______/  |__|  |__|  \______/  |__|\__\ /__/     \__\ 
"""
LINE = '-' * 18
INFO = " " * 7 + 'Developed by Mikoris | For more help, type /help'


def _agent_loop(work_bot, response, file_contents: dict,
                input_tokens: int, output_tokens: int, round_count: int) -> tuple[bool, dict, int, int, int]:
    """执行工具调用循环，直到 finish 或 Bot 返回纯文本（等待用户输入）。"""
    while True:
        text_content: str = response['content']
        tool_calls: list = response['tool_calls']
        interrupted: bool = response.get('interrupted', False)

        # ── 情形A：有工具调用 ──────────────────────────────────────────
        if tool_calls:
            if text_content:
                user_log(text_content, role='BOT')

            is_finish, file_contents = tools.execute_tool_calls(work_bot, tool_calls)
            if is_finish:
                log('work DONE')
                return True, file_contents, input_tokens, output_tokens, round_count

            # 工具执行完毕后检查中断：不再继续 resume，交还控制权
            if interrupted:
                return False, file_contents, input_tokens, output_tokens, round_count

            response = work_bot.resume(use_tools=True)
            input_tokens += response.get('input_tokens', 0)
            output_tokens += response.get('output_tokens', 0)
            round_count += 1

            # resume 跑完后再次检查（用户在 resume 期间按了 ESC）
            if response.get('interrupted'):
                if response['content']:
                    user_log(response['content'], role='BOT')
                return False, file_contents, input_tokens, output_tokens, round_count

            continue

        # ── 情形B：纯文本，交还控制权给用户 ───────────────────────────
        if text_content:
            user_log(text_content, role='BOT')
        return False, file_contents, input_tokens, output_tokens, round_count


if __name__ == '__main__':
    try:
        from rich.console import Console as _Console
        from rich.panel import Panel as _Panel
        from rich.text import Text as _Text
        _con = _Console(highlight=False)
        _footer = "\n" + " " * 19 + 'Welcome back! This is Momoka~'
        _con.print(_Panel(
            TITLE.strip() + '\n' + _footer,
            border_style='bright_cyan', padding=(0, 2), expand=False,
            subtitle=INFO.strip(), subtitle_align='center',
        ))
    except Exception:
        print(TITLE + INFO + '\n' + LINE + ' Welcome back! This is Momoka ' + LINE)
    new_log()
    log('start')

    work_bot = bot.Bot(bot_name='Momoka')
    work_bot.set_system(build_system_prompt())

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
            print("-" * 73)
            print(f'Done ({time_str} | Input: {input_tokens} tokens | Output: {output_tokens} tokens | {round_count}R)')
            log('end')
            break

        handled, skill_name = handle_slash(
            user_message, input_tokens, output_tokens, round_count, start_time
        )

        if handled and skill_name is None:
            continue

        if handled and skill_name is not None:
            log(f'skill trigger: {skill_name}')
            skill_result, skill_fc, _ = tools._execute_tool(
                'get_skill', {'skill_name': skill_name}
            )
            if skill_fc:
                # 将 skill 内容注入 system prompt
                work_bot.inject_skill(skill_name, skill_result)
                log(f'system (skill inject): {skill_name}')
                continue  # 等待用户的下一条指令
            else:
                user_log(skill_result, role='ERROR')
                continue
        else:
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
            work_bot.clear_skills()
            user_log('Ready')