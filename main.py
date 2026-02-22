from logger import log, user_log, new_log
import bot_io
from config import get_config
import bot
from system_io import get_cwd

TITLE = r"""
.___  ___.   ______   .___  ___.   ______   __  ___       ___      
|   \/   |  /  __  \  |   \/   |  \  /  | | |/  /        /   \     
|  \  /  | |  |  |  | |  \  /  | |  |  |  | |  '  /     /  ^  \    
|  |\/|  | |  |  |  | |  |\/|  | |  |  |  | |    <     /  /_\  \   
|  |  |  | |  `--'  | |  |  |  | |  `--'  | |  .  \   /  _____  \  
|__|  |__|  \______/  |__|  |__|  \______/  |__|\__\ /__/     \__\ 
"""
LINE = '-' * 21


def _build_prompt(request: str) -> str:
    """根据当前配置构建工作提示词。"""
    cfg = get_config()
    return (
        f"你是Momoka，一个工作助理。你需要操作用户的电脑并完成用户的需求。\n"
        f"用户的需求：\n{request}\n"
        f"你当前所在的目录：{get_cwd()}\n"
        f"是否处于文件编辑模式：{cfg['edit_mode']}\n"
        f"是否处于替换模式：{cfg.get('replace_mode', False)}"
        + (f"（步骤：{'等待旧文本' if cfg.get('replace_step') == 1 else '等待新文本'}，文件：{cfg.get('replace_file')}）" if cfg.get('replace_mode') else "") + "\n"
        "如果你不处于文件编辑模式，请给出以下操作指令：\n"
        '操作用户的CMD终端："{SYSTEM [command]}"，例如"{SYSTEM dir}"或"{SYSTEM mkdir example_dir}"；\n'
        '进入文件编辑模式以编辑文件："{EDIT [file name]}"。文件名请使用绝对路径并添加拓展名；\n'
        '进入替换模式以替换文件中的文本："{REPLACE [file name]}"。文件名请使用绝对路径并添加拓展名；\n'
        '  替换模式为两步流程：进入后先输出要被替换的旧文本，系统确认后再输出替换成的新文本。\n'
        '阅读文件内容："{READ [file name]}"。文件名请使用绝对路径并添加拓展名，不支持通配符；\n'
        '切换目录："{CD [path]}"，例如"{CD temp}"或"{CD C:\\absolute\\path}"；\n'
        '在需要时询问用户："{ASK [question]}"，例如"{ASK 请告诉我网站密码}"；\n'
        '在需要时向用户报告步骤规划、执行情况等："{REPORT [report]}"，例如"{REPORT 为了完成需求，我将...}"；\n'
        '向用户发送消息："{OUTPUT [output]}"，例如"{OUTPUT 统计结果为...}"；\n'
        '向用户交付工作成果："{FINISH}"\n'
        "\n"
        "── 浏览器操作指令（使用 Chromium 浏览器）──\n"
        '打开网页："{BROWSE_OPEN [URL]}"，例如"{BROWSE_OPEN https://www.baidu.com}"；\n'
        '读取当前页面文字内容："{BROWSE_READ}"，或指定最大字符数"{BROWSE_READ 8000}"；\n'
        '点击页面元素（CSS选择器）："{BROWSE_CLICK [selector]}"，例如"{BROWSE_CLICK #submit}"；\n'
        '在输入框中输入文字："{BROWSE_TYPE [selector]|[text]}"，例如"{BROWSE_TYPE #kw|Python教程}"；\n'
        '操作下拉框："{BROWSE_SELECT [selector]|[选项值/文字/序号]}"，例如"{BROWSE_SELECT #lang|zh-CN}"；\n'
        '悬停元素（触发 tooltip 或展开菜单）："{BROWSE_HOVER [selector]}"，例如"{BROWSE_HOVER .menu-item}"；\n'
        '浏览器后退："{BROWSE_BACK}"；\n'
        '浏览器前进："{BROWSE_FORWARD}"；\n'
        '在页面中搜索文字并返回匹配元素："{BROWSE_FIND [文字]}"，或限制结果数"{BROWSE_FIND [文字]|[数量]}"；\n'
        '下载文件到工作目录："{BROWSE_DOWNLOAD [URL]}"，或指定保存目录"{BROWSE_DOWNLOAD [URL]|[目录]}"；\n'
        '上传本地文件到输入框："{BROWSE_UPLOAD [selector]|[文件路径]}"，例如"{BROWSE_UPLOAD #file-input|C:\\\\file.pdf}"；\n'
        '将当前页面导出为 PDF："{BROWSE_PDF}"，或指定保存目录"{BROWSE_PDF [目录]}"；\n'
        '截图并保存到工作目录："{BROWSE_SHOT}"，或指定路径"{BROWSE_SHOT C:\\\\screenshots}"；\n'
        '执行 JavaScript："{BROWSE_EVAL [js expression]}"，例如"{BROWSE_EVAL document.title}"；\n'
        '关闭浏览器："{BROWSE_CLOSE}"\n'
        "注意：浏览器操作完成后，建议使用 BROWSE_READ 确认结果，再决定下一步。\n"
        "\n"
        f"你的工作目录是：{cfg['work_dir']}，请在工作目录中进行操作。\n"
        "*注意：如果需要操作工作目录之外的文件，请征得用户的同意*。\n"
        "直接输出操作指令，不要解释。操作指令需要用{}包裹。\n"
        "如果你处于文件编辑模式，请输出写入文件的内容。*注意：你写入的内容将全部覆盖原有文件内容。*\n"
        "如果你处于替换模式，请输出纯文本（旧文本或新文本）。*注意：你输出的内容将直接作为替换或被替换内容。*"
    )


def work(request: str):
    """驱动 Bot 循环执行操作，直到输出 FINISH；随后进入自由对话模式。"""
    work_bot = bot.Bot()
    work_bot.set_system(_build_prompt(request))

    # ── 自动执行阶段 ────────────────────────────────────────────────────
    parsed_output = '请开始操作。'
    touched_files: list[str] = []  # 上一轮涉及的文件（初始为空，不触发折叠）

    while True:
        # 在把 parsed_output 发送给 Bot 之前，先折叠历史中的旧文件内容
        # （此时 parsed_output 已包含最新文件内容，历史中的旧版本可以折叠）
        # 去重，避免同一轮多次读同一文件时重复调用折叠
        if get_config().get('fold', True):
            for filename in dict.fromkeys(touched_files):
                count = work_bot.collapse_file_in_history(filename)
                if count:
                    log(f'折叠：{filename}（折叠了 {count} 条旧记录）')

        bot_output = work_bot.message(parsed_output, role='user')
        parsed_output, touched_files = bot_io.parse(bot_output)

        if parsed_output == 'FINISH':
            user_log('Done')
            log('work DONE')
            break

    # ── 自由对话阶段 ────────────────────────────────────────────────────
    cfg = get_config()

    if not cfg['summary'] and not cfg['dialogue']:
        return

    work_bot.set_system('你是Momoka，一个工作助理。你现在需要回答用户的问题。*不用格式化输出*')

    if cfg['summary']:
        user_log('Bot的工作已完成，正在生成总结...')
        user_log(work_bot.message('总结你刚才进行的工作', role='user'), role='BOT')

    if cfg['dialogue']:
        user_log('现在你可以与 Bot 交流（输入 "/end" 结束）')
        while True:
            user_input = input('>> ')
            if user_input == '/end':
                user_log('结束')
                log('end')
                break
            user_log(work_bot.message(user_input, role='user'), role='BOT')


if __name__ == '__main__':
    print(TITLE + '\n' + LINE + '欢迎回来！这里是Momoka v0.1' + LINE)
    new_log()
    log('start')

    request = input('请输入你的需求: ')
    user_log('开始')
    work(request)