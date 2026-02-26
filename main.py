from logger import log, user_log, new_log
import bot_io
from config import get_config
import bot
from system_io import get_cwd

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
    """支持多行输入：行末输入 '\' 后回车可继续下一行，否则结束输入。"""
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


def _build_system_prompt(request: str) -> str:
    """根据当前配置构建 system 提示词（work 阶段）。"""
    cfg = get_config()
    return (
        f"你是 Momoka，一个工作助理。你需要通过调用工具来操作用户的电脑并完成需求。\n"
        f"用户的需求：\n{request}\n\n"
        f"当前工作目录：{get_cwd()}\n"
        f"工作目录（基准）：{cfg['work_dir']}\n\n"
        "规则：\n"
        f"- 称呼用户为“{get_config()['user_call']}”。\n" if get_config()['user_call'] is not None else ""
        "- 优先在工作目录中进行操作；如需操作工作目录之外的文件，请先通过 ask_user 征得同意。\n"
        "- 每次调用工具时，请在工具调用之前附上一句简短的说明文字，告知用户你正在做什么或为什么这样做。\n"
        "- 浏览器操作后，建议调用 browse_read 确认结果，再决定下一步。\n"
        "- 完成所有工作后，调用 finish 交付成果。\n"
        "- 进入文件编辑模式后，下一条消息请只输出文件的完整内容，不要使用工具调用。\n"
        "- 进入替换模式后，下一条消息请只输出旧文本，确认后再输出新文本，不要使用工具调用。\n"
    )


def work(request: str):
    """驱动 Bot 循环执行操作，直到调用 finish；随后可进入自由对话模式。"""
    work_bot = bot.Bot(bot_name='Momoka')
    work_bot.set_system(_build_system_prompt(request))

    file_contents: dict[str, str] = {}

    # 首次用 message() 插入 user 消息触发模型开始；后续工具执行完用 resume() 续推理
    response = work_bot.message(
        '请开始操作。',
        role='user',
        file_contents=file_contents,
        use_tools=True,
    )

    while True:
        text_content: str = response['content']
        tool_calls: list = response['tool_calls']

        # ── 情形A：有工具调用 ────────────────────────────────────────────
        if tool_calls:
            if text_content:
                user_log(text_content, role='BOT REPORT')

            # 折叠上一轮读取的文件
            cfg = get_config()
            if cfg.get('fold', True):
                for filename in file_contents:
                    count = work_bot.collapse_file_in_history(filename)
                    if count:
                        log(f'折叠：{filename}（折叠了 {count} 条旧记录）')

            is_finish, file_contents = bot_io.execute_tool_calls(work_bot, tool_calls)
            if is_finish:
                user_log('Done')
                log('work DONE')
                break

            # 工具执行完，直接续推理，不插 user 消息
            response = work_bot.resume(use_tools=True)
            continue

        # ── 情形B：纯文本兜底（无工具调用）──────────────────────────────
        if text_content:
            user_log(text_content, role='BOT REPORT')
        response = work_bot.message('请继续完成任务，记得使用工具调用。', use_tools=True)

    # ── 自由对话阶段 ────────────────────────────────────────────────────
    cfg = get_config()
    if not cfg.get('summary') and not cfg.get('dialogue'):
        return

    work_bot.set_system('你是 Momoka，一个工作助理。你现在需要回答用户的问题。不用格式化输出。')

    if cfg.get('summary'):
        user_log('Bot 的工作已完成，正在生成总结...')
        res = work_bot.message('总结你刚才进行的工作', use_tools=False)
        user_log(res['content'], role='BOT')

    if cfg.get('dialogue'):
        user_log('现在你可以与 Bot 交流（输入 /end 结束）')
        while True:
            user_input = multiline_input('>> ')
            if user_input.strip() == '/end':
                user_log('结束')
                log('end')
                break
            res = work_bot.message(user_input, use_tools=False)
            user_log(res['content'], role='BOT')


if __name__ == '__main__':
    print(TITLE + '\n' + LINE + ' 欢迎回来！这里是 Momoka v0.1 ' + LINE)
    new_log()
    log('start')

    request = multiline_input('请输入你的需求（行末输入 \\ 可换行）: ')
    user_log('开始')
    work(request)
