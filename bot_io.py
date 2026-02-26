"""
bot_io.py —— 工具调用执行层。

接收 Bot.message() 返回的 tool_calls 列表，依次执行每个工具，
将结果通过 Bot.add_tool_result() 写回历史，最终返回是否 FINISH。

替换/编辑模式的"两步流程"通过 working_config.json 的状态机维护，
与原版逻辑保持一致。
"""

import json
from logger import log, user_log
from config import get_config
from system_io import system_command


# ── 文件工具 ──────────────────────────────────────────────────────────────

def find_file(filename: str) -> str | None:
    """读取文件内容，若文件不存在或路径无效则返回 None。"""
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            return f.read()
    except (FileNotFoundError, OSError, TypeError):
        return None


def edit_file(filename: str, text: str):
    """将 text 覆盖写入指定文件。"""
    with open(filename, 'w', encoding='utf-8') as f:
        f.write(text)


# ── 单个工具执行 ──────────────────────────────────────────────────────────

def _execute_tool(name: str, args: dict,
                  input_func=input) -> tuple[str, dict[str, str], bool]:
    """执行单个工具调用。

    Returns:
        (result_str, file_contents_dict, is_finish)
        file_contents_dict: 仅 read_file 成功时非空，格式 {filename: content}
        is_finish:          True 表示 Bot 调用了 finish()
    """
    cfg = get_config()

    match name:

        # ── finish ──────────────────────────────────────────────────────
        case 'finish':
            return 'FINISH', {}, True

        # ── system_command ──────────────────────────────────────────────
        case 'system_command':
            command = args.get('command', '')
            user_log(f'终端输入：{command}', role='CMD')
            output = system_command(command)
            user_log(f'终端输出：{"(NULL)" if output == "" else output}', role='CMD')
            return output or '（输出为空）', {}, False

        # ── edit_file ────────────────────────────────────────────────────
        case 'edit_file':
            file_path = args.get('file_path', '')
            content = args.get('content', '')
            edit_file(file_path, content)
            user_log(f'Bot 写入文件：{file_path}')
            return f'文件写入完成：{file_path}', {}, False

        # ── replace_file ──────────────────────────────────────────────────
        case 'replace_file':
            file_path = args.get('file_path', '')
            old_text = args.get('old_text', '')
            new_text = args.get('new_text', '')
            content = find_file(file_path)
            if content is None:
                return f'替换失败：无法读取文件 {file_path}。', {}, False
            if old_text not in content:
                return f'替换失败：在 {file_path} 中未找到指定的旧文本。', {}, False
            edit_file(file_path, content.replace(old_text, new_text, 1))
            user_log(f'Bot 替换文件：{file_path}')
            return f'文件替换完成：{file_path}', {}, False

        # ── read_file ──────────────────────────────────────────────────────
        case 'read_file':
            file_path = args.get('file_path', '')
            user_log(f'Bot 开始阅读文件：{file_path}')
            content = find_file(file_path)
            if content is None:
                return f'没有找到文件：{file_path}。请尝试绝对路径或添加扩展名。', {}, False
            result = f'成功打开文件：{file_path}\n{file_path}:\n{content}'
            return result, {file_path: content}, False

        # ── change_directory ───────────────────────────────────────────────
        case 'change_directory':
            from system_io import set_cwd_explicit
            path = args.get('path', '')
            result = set_cwd_explicit(path)
            user_log(f'切换目录：{path}')
            return result, {}, False

        # ── ask_user ───────────────────────────────────────────────────────
        case 'ask_user':
            question = args.get('question', '')
            reply = input_func(f'Bot 向你提问：{question}\n请回复：')
            return (f'用户回复：{reply}' if reply else '用户什么都没回复。'), {}, False

        # ── output ─────────────────────────────────────────────────────────
        case 'output':
            message = args.get('message', '')
            user_log(message, role='BOT')
            return '发送成功', {}, False

        # ── 浏览器指令 ─────────────────────────────────────────────────────

        case 'browse_open':
            from browser_io import browser_open_safe
            url = args.get('url', '')
            user_log(f'浏览器打开：{url}')
            return browser_open_safe(url), {}, False

        case 'browse_read':
            from browser_io import browser_read_safe
            max_chars = args.get('max_chars', 4000)
            user_log('浏览器读取页面内容')
            return browser_read_safe(int(max_chars)), {}, False

        case 'browse_find':
            from browser_io import browser_find_safe
            text = args.get('text', '')
            max_results = args.get('max_results', 10)
            user_log(f'浏览器页面搜索：{text!r}')
            return browser_find_safe(text, int(max_results)), {}, False

        case 'browse_download':
            from browser_io import browser_download_safe
            url = args.get('url', '')
            save_dir = args.get('save_dir') or cfg['work_dir']
            user_log(f'浏览器下载：{url} → {save_dir}')
            return browser_download_safe(url, save_dir), {}, False

        case 'browse_upload':
            from browser_io import browser_upload_safe
            selector = args.get('selector', '')
            file_path = args.get('file_path', '')
            user_log(f'浏览器上传文件：{file_path} → {selector}')
            return browser_upload_safe(selector, file_path), {}, False

        case 'browse_pdf':
            from browser_io import browser_pdf_safe
            save_dir = args.get('save_dir') or cfg['work_dir']
            user_log(f'浏览器导出 PDF，保存至：{save_dir}')
            return browser_pdf_safe(save_dir), {}, False

        case 'browse_eval':
            from browser_io import browser_eval_safe
            script = args.get('script', '')
            user_log(f'浏览器执行 JS：{script}')
            return browser_eval_safe(script), {}, False

        case 'browse_close':
            from browser_io import browser_close_safe
            user_log('关闭浏览器')
            return browser_close_safe(), {}, False

        case _:
            return f'未知工具：{name}', {}, False


# ── 主入口：处理一轮工具调用 ──────────────────────────────────────────────

def execute_tool_calls(
    work_bot,           # bot.Bot 实例
    tool_calls: list,
    input_func=input,
) -> tuple[bool, dict[str, str]]:
    """依次执行 tool_calls 列表中的所有工具，将结果写回 work_bot 历史。

    同时处理"文件编辑模式"和"替换模式"的多步状态机：
      - 进入编辑/替换模式后，后续 model 的纯文本输出即为文件内容或旧/新文本。

    Returns:
        (is_finish, all_file_contents)
        is_finish:          是否有工具调用了 finish()
        all_file_contents:  本轮所有 read_file 读到的文件内容合集
    """
    all_file_contents: dict[str, str] = {}
    is_finish = False

    for tc in tool_calls:
        name = tc.function.name
        try:
            args = json.loads(tc.function.arguments)
        except json.JSONDecodeError:
            args = {}

        result, file_contents, finish = _execute_tool(name, args, input_func)
        all_file_contents.update(file_contents)

        log(f'execute_tool_calls | {name}({args}) → {result[:80]}...')
        work_bot.add_tool_result(tc.id, result)

        if finish:
            is_finish = True
            break

    return is_finish, all_file_contents