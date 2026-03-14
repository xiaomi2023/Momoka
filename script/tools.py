"""
tools.py —— 工具调用执行层。

接收 Bot.message() 返回的 tool_calls 列表，依次执行每个工具，
将结果通过 Bot.add_tool_result() 写回历史，最终返回是否 FINISH。

替换/编辑模式的"两步流程"通过 working_config.json 的状态机维护，
与原版逻辑保持一致。
"""

import json
import traceback
from logger import log, user_log
from config import get_config
from script.system import system_command, find_file, edit_file


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
    default_encoding: str = cfg.get('encoding', 'utf-8')

    match name:

        # ── set_wait ────────────────────────────────────────────────────
        case 'set_wait':
            from config import set_wait
            seconds = int(args.get('seconds', 10))
            set_wait(seconds)
            user_log(f'超时时长已设置为: {seconds} 秒')
            return f'超时时长已更新为 {seconds} 秒', {}, False

        # ── finish ──────────────────────────────────────────────────────
        case 'finish':
            return 'FINISH', {}, True

        # ── system_command ──────────────────────────────────────────────
        case 'system_command':
            command = args.get('command', '')
            inputs = args.get('inputs')  # 获取新参数
            user_log(f'终端输入: {command}{f' | input={inputs}' if inputs is not None else ""}', role='CMD')
            output = system_command(command, inputs=inputs)
            user_log(f'终端输出: {"(NULL)" if output == "" else ("\n" + output)}', role='CMD')
            return output or '（输出为空）', {}, False

        # ── edit_file ────────────────────────────────────────────────────
        case 'edit_file':
            file_path = args.get('file_path', '')
            content = args.get('content', '')
            encoding = args.get('encoding') or default_encoding
            try:
                edit_file(file_path, content, encoding)
                write_lines = len(content.splitlines())
                user_log(f'Bot 写入文件: {file_path} (+{write_lines})')
                return f'文件写入完成: {file_path}（+{write_lines} 行）', {}, False
            except Exception as e:
                log(f'edit_file error | {file_path}\n{traceback.format_exc()}')
                return f'在编辑文件时遇到了以下错误: \n{type(e).__name__}: {e}\n如果没有找到文件，可以尝试使用文件的绝对路径。', {}, False

        # ── replace_file ──────────────────────────────────────────────────
        case 'replace_file':
            file_path = args.get('file_path', '')
            old_text = args.get('old_text', '')
            new_text = args.get('new_text', '')
            encoding = args.get('encoding') or default_encoding
            try:
                content = find_file(file_path, encoding)
                if old_text not in content:
                    return f'替换失败: 在 {file_path} 中未找到指定的旧文本。', {}, False
                new_content = content.replace(old_text, new_text, 1)
                edit_file(file_path, new_content, encoding)
                old_lines = len(old_text.splitlines())
                new_lines = len(new_text.splitlines())
                user_log(f'Bot 替换文件: {file_path} (-{old_lines},+{new_lines})')
                return f'文件替换完成: {file_path}（-{old_lines} 行，+{new_lines} 行）', {}, False
            except Exception as e:
                log(f'replace_file error | {file_path}\n{traceback.format_exc()}')
                return f'在替换文件时遇到了以下错误: \n{type(e).__name__}: {e}\n如果没有找到文件，可以尝试使用文件的绝对路径。', {}, False

        # ── read_file ──────────────────────────────────────────────────────
        case 'read_file':
            file_path = args.get('file_path', '')
            encoding = args.get('encoding') or default_encoding
            user_log(f'Bot 阅读文件: {file_path}')
            try:
                import os as _os
                file_size = _os.path.getsize(file_path)
                if file_size > 100 * 1024:
                    kb = file_size / 1024
                    return (f'文件过大: {file_path}（{kb:.1f} KB）。'
                            f'你可以使用其他方式（例如: 随机读取文件的部分内容）阅读此文件。'), {}, False
                content = find_file(file_path, encoding)
                line_count = len(content.splitlines())
                if line_count > 1000:
                    return (f'文件过大: {file_path}（共 {line_count} 行）。'
                            f'你可以使用其他方式（例如: 随机读取文件的部分内容）阅读此文件。'), {}, False
                result = f'成功打开文件: {file_path}\n{file_path}:\n{content}'
                return result, {file_path: content}, False
            except Exception as e:
                log(f'read_file error | {file_path}\n{traceback.format_exc()}')
                return f'在阅读文件时遇到了以下错误: \n{type(e).__name__}: {e}\n如果没有找到文件，可以尝试使用文件的绝对路径。', {}, False

        # ── change_directory ───────────────────────────────────────────────
        case 'change_directory':
            from script.system import set_cwd_explicit
            path = args.get('path', '')
            result = set_cwd_explicit(path)
            user_log(f'切换目录: {path}')
            return result, {}, False

        # ── ask_user ───────────────────────────────────────────────────────
        case 'ask_user':
            question = args.get('question', '')
            user_log(f'{question}', role='QUESTION')
            reply = input_func(f'>> ')
            return (f'用户回复: {reply}' if reply else '用户什么都没回复。'), {}, False

        # ── 浏览器指令 ─────────────────────────────────────────────────────

        case 'browse_open':
            from script.browser import browser_open
            url = args.get('url', '')
            user_log(f'打开网页: {url}')
            return browser_open(url), {}, False

        case 'browse_search':
            from script.browser import browser_search
            query = args.get('query', '')
            engine = args.get('engine', 'google')
            user_log(f'搜索 [{engine}]: {query}')
            return browser_search(query, engine), {}, False

        case 'browse_read':
            from script.browser import browser_read
            max_chars = args.get('max_chars', 4000)
            user_log('读取网页内容...')
            return browser_read(int(max_chars)), {}, False

        case 'browse_find':
            from script.browser import browser_find
            text = args.get('text', '')
            max_results = args.get('max_results', 10)
            user_log(f'页面搜索...: {text!r}')
            return browser_find(text, int(max_results)), {}, False

        case 'browse_download':
            from script.browser import browser_download
            url = args.get('url', '')
            save_dir = args.get('save_dir') or cfg['work_dir']
            user_log(f'下载文件...: {url} → {save_dir}')
            return browser_download(url, save_dir), {}, False

        case 'browse_upload':
            from script.browser import browser_upload
            selector = args.get('selector', '')
            file_path = args.get('file_path', '')
            user_log(f'上传文件...: {file_path} → {selector}')
            return browser_upload(selector, file_path), {}, False

        case 'browse_pdf':
            from script.browser import browser_pdf
            save_dir = args.get('save_dir') or cfg['work_dir']
            user_log(f'已将网页导出为 PDF，保存至: {save_dir}')
            return browser_pdf(save_dir), {}, False

        case 'browse_eval':
            from script.browser import browser_eval
            script = args.get('', '')
            user_log(f'执行 JS: {script}')
            return browser_eval(script), {}, False

        case 'browse_wait_for_navigation':
            from script.browser import browser_wait_for_navigation
            timeout = args.get('timeout')
            state = args.get('state', 'networkidle')
            user_log(f'网页加载({state})')
            return browser_wait_for_navigation(timeout, state), {}, False

        case 'browse_switch':
            from script.browser import browser_switch
            index = int(args.get('index', 0))
            user_log(f'切换标签页: [{index}]')
            return browser_switch(index), {}, False

        case 'browse_close':
            from script.browser import browser_close
            user_log('关闭浏览器')
            return browser_close(), {}, False

        case _:
            return f'未知工具: {name}', {}, False


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

        log(f'execute_tool_calls | {name}({args}) → {result}')
        work_bot.add_tool_result(tc.id, result,
                                 file_contents=file_contents if file_contents else None)

        if finish:
            is_finish = True
            break

    return is_finish, all_file_contents