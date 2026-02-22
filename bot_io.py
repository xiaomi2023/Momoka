from logger import log, user_log
from config import get_config, set_edit_mode, set_file_name
from system_io import system_command


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


def extract_braces(command: str) -> str | None:
    """提取命令字符串中第一对 {} 内的内容，未找到则返回 None。"""
    left = command.find('{')
    right = command.rfind('}')
    if left == -1 or right == -1:
        return None
    return command[left + 1:right]


def extract_all_braces(command: str) -> list[str]:
    """按先后顺序提取命令字符串中所有 {} 内的内容，返回列表（可能为空）。"""
    results = []
    i = 0
    while i < len(command):
        left = command.find('{', i)
        if left == -1:
            break
        right = command.find('}', left + 1)
        if right == -1:
            break
        results.append(command[left + 1:right])
        i = right + 1
    return results


def _parse_single(inner: str, input_func=input) -> tuple[str, list[str]]:
    """
    执行单条已提取的指令（{} 内的内容）。

    返回：(执行结果字符串, 本次涉及的文件名列表)
    只有 READ 和 EDIT 成功打开文件时，文件名列表才非空。
    """
    parts = inner.split(maxsplit=1)
    cmd_type = parts[0]
    inp = parts[1] if len(parts) > 1 else None

    match cmd_type:
        case 'FINISH':
            return 'FINISH', []

        case 'SYSTEM':
            user_log(f'终端输入：{inp}')
            output = system_command(inp)
            user_log(f'终端输出：{"(NULL)" if output == "" else output}')
            return output or '（输出为空）', []

        case 'EDIT':
            set_edit_mode(True)
            set_file_name(inp)
            user_log(f'Bot开始编辑文件：{inp}')
            content = find_file(inp)
            hint = '（文件不存在或为空）' if content is None else inp
            return f'成功打开文件：{hint}，你已进入文件编辑模式。', []

        case 'REPLACE':
            from config import set_replace_mode, set_replace_file, set_replace_step, set_replace_old_text
            set_replace_mode(True)
            set_replace_file(inp)
            set_replace_step(1)
            set_replace_old_text('')
            user_log(f'Bot开始替换文件：{inp}')
            content = find_file(inp)
            hint = '（文件不存在或为空）' if content is None else inp
            return f'成功打开文件：{hint}，你已进入替换模式。请输出要被替换的旧文本。', []

        case 'READ':
            user_log(f'Bot开始阅读文件：{inp}')
            content = find_file(inp)
            if content is None:
                return f'没有找到文件：{inp}。请尝试绝对路径或添加扩展名。', []
            result = f'成功打开文件：{inp}\n{inp}:\n{content}'
            # 文件成功读取，记录文件名供折叠使用
            return result, [inp]

        case 'CD':
            from system_io import set_cwd_explicit
            result = set_cwd_explicit(inp)
            user_log(f'切换目录：{inp}')
            return result, []

        case 'ASK':
            reply = input_func(f'Bot向你提问：{inp}\n请回复：')
            return (f'用户回复：{reply}' if reply else '用户什么都没回复。'), []

        case 'OUTPUT':
            user_log(inp, role='BOT')
            return '发送成功', []

        case 'REPORT':
            user_log(inp, role='BOT REPORT')
            return '发送成功', []

        # ── 浏览器指令 ────────────────────────────────────────────────────

        case 'BROWSE_OPEN':
            from browser_io import browser_open_safe
            user_log(f'浏览器打开：{inp}')
            return browser_open_safe(inp), []

        case 'BROWSE_READ':
            from browser_io import browser_read_safe
            user_log('浏览器读取页面内容')
            max_chars = int(inp) if inp and inp.isdigit() else 4000
            return browser_read_safe(max_chars), []

        case 'BROWSE_CLICK':
            from browser_io import browser_click_safe
            user_log(f'浏览器点击：{inp}')
            return browser_click_safe(inp), []

        case 'BROWSE_TYPE':
            from browser_io import browser_type_safe
            if inp and '|' in inp:
                selector, text = inp.split('|', 1)
                user_log(f'浏览器输入文字：{selector} <- {text!r}')
                return browser_type_safe(selector.strip(), text), []
            return 'BROWSE_TYPE 格式错误，请使用：{BROWSE_TYPE 选择器|输入文字}', []

        case 'BROWSE_SHOT':
            from browser_io import browser_screenshot_safe
            from config import get_config as _cfg
            save_dir = inp or _cfg()['work_dir']
            user_log(f'浏览器截图，保存至：{save_dir}')
            return browser_screenshot_safe(save_dir), []

        case 'BROWSE_EVAL':
            from browser_io import browser_eval_safe
            user_log(f'浏览器执行 JS：{inp}')
            return browser_eval_safe(inp), []

        case 'BROWSE_CLOSE':
            from browser_io import browser_close_safe
            user_log('关闭浏览器')
            return browser_close_safe(), []

        case 'BROWSE_SELECT':
            from browser_io import browser_select_safe
            # 格式：{BROWSE_SELECT selector|value}
            if inp and '|' in inp:
                selector, value = inp.split('|', 1)
                user_log(f'浏览器下拉框选择：{selector} = {value!r}')
                return browser_select_safe(selector.strip(), value), []
            return 'BROWSE_SELECT 格式错误，请使用：{BROWSE_SELECT 选择器|选项值}', []

        case 'BROWSE_HOVER':
            from browser_io import browser_hover_safe
            user_log(f'浏览器悬停：{inp}')
            return browser_hover_safe(inp), []

        case 'BROWSE_BACK':
            from browser_io import browser_back_safe
            user_log('浏览器后退')
            return browser_back_safe(), []

        case 'BROWSE_FORWARD':
            from browser_io import browser_forward_safe
            user_log('浏览器前进')
            return browser_forward_safe(), []

        case 'BROWSE_FIND':
            from browser_io import browser_find_safe
            # 可选格式：{BROWSE_FIND 搜索文字} 或 {BROWSE_FIND 搜索文字|最大结果数}
            if inp and '|' in inp:
                text, max_r = inp.rsplit('|', 1)
                max_results = int(max_r.strip()) if max_r.strip().isdigit() else 10
            else:
                text, max_results = inp, 10
            user_log(f'浏览器页面搜索：{text!r}')
            return browser_find_safe(text.strip(), max_results), []

        case 'BROWSE_DOWNLOAD':
            from browser_io import browser_download_safe
            from config import get_config as _cfg
            # 可选格式：{BROWSE_DOWNLOAD URL} 或 {BROWSE_DOWNLOAD URL|保存目录}
            if inp and '|' in inp:
                url, save_dir = inp.split('|', 1)
            else:
                url, save_dir = inp, _cfg()['work_dir']
            user_log(f'浏览器下载：{url.strip()} → {save_dir.strip()}')
            return browser_download_safe(url.strip(), save_dir.strip()), []

        case 'BROWSE_UPLOAD':
            from browser_io import browser_upload_safe
            # 格式：{BROWSE_UPLOAD selector|文件路径}
            if inp and '|' in inp:
                selector, file_path = inp.split('|', 1)
                user_log(f'浏览器上传文件：{file_path.strip()} → {selector.strip()}')
                return browser_upload_safe(selector.strip(), file_path.strip()), []
            return 'BROWSE_UPLOAD 格式错误，请使用：{BROWSE_UPLOAD 选择器|本地文件路径}', []

        case 'BROWSE_PDF':
            from browser_io import browser_pdf_safe
            from config import get_config as _cfg
            save_dir = inp or _cfg()['work_dir']
            user_log(f'浏览器导出 PDF，保存至：{save_dir}')
            return browser_pdf_safe(save_dir), []

        case _:
            return f'未知指令类型：{cmd_type}', []


def parse(command: str, input_func=input) -> tuple[str, list[str]]:
    """
    解析 Bot 输出的操作指令并执行，支持多条 {} 指令按序执行，结果依次拼接。

    返回：(执行结果字符串, 本轮涉及的文件名列表)
    调用方可根据文件名列表决定是否对历史记录执行折叠。
    """
    log('start to parse: ' + command)
    cfg = get_config()

    # ── 替换模式步骤1：接收旧文本 ────────────────────────────────────────
    if cfg.get('replace_mode') and cfg.get('replace_step') == 1:
        from config import set_replace_step, set_replace_old_text
        set_replace_old_text(command)
        set_replace_step(2)
        return '旧文本已记录，请输出要替换成的新文本。', []

    # ── 替换模式步骤2：接收新文本并执行替换 ────────────────────────────
    if cfg.get('replace_mode') and cfg.get('replace_step') == 2:
        from config import set_replace_mode, set_replace_file, set_replace_step, set_replace_old_text
        filename = cfg.get('replace_file', '')
        old_text = cfg.get('replace_old_text', '')
        new_text = command
        content = find_file(filename)
        if content is None:
            set_replace_mode(False)
            return f'替换失败：无法读取文件 {filename}。', []
        if old_text not in content:
            set_replace_mode(False)
            return f'替换失败：在 {filename} 中未找到指定的旧文本。', [filename]
        new_content = content.replace(old_text, new_text)
        edit_file(filename, new_content)
        set_replace_mode(False)
        set_replace_step(1)
        set_replace_old_text('')
        user_log(f'文件替换完成：{filename}')
        result = f'文件替换完成：{filename}'
        return result, [filename]

    # ── 文件编辑模式：整个输出即为文件内容 ──────────────────────────────
    if cfg['edit_mode']:
        filename = cfg['file_name']
        edit_file(filename, command)
        set_edit_mode(False)
        user_log(f'文件编辑完成：{filename}')
        result = (f'文件编辑完成，以下为 {filename} 的新内容：'
                  f'\n{find_file(filename)}')
        # 编辑完成后，将文件名纳入本轮 touched_files，触发折叠检查
        return result, [filename]

    # ── 普通模式：提取所有 {} 指令并依次执行 ────────────────────────────
    inners = extract_all_braces(command)
    if not inners:
        return '在解析命令时出现问题：没有解析到"{}"', []

    results = []
    all_touched: list[str] = []

    for idx, inner in enumerate(inners):
        result, touched = _parse_single(inner, input_func)

        # FINISH 直接短路返回，不再执行后续指令
        if result == 'FINISH':
            return 'FINISH', all_touched

        results.append(f'<尝试执行第{idx + 1}条指令 ({inner})>\n{result}')
        all_touched.extend(touched)

        # EDIT 进入文件编辑模式后后续指令无意义，提前结束
        if get_config()['edit_mode']:
            break

    return '\n\n'.join(results), all_touched