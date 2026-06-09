"""
server/servers/send_file/send_file.py — Send File tool handler.

send_file 工具处理器：
- Bot 平台（Lark/Discord/QQ）：以附件形式发送文件
- CLI/Headless 模式：读取文件内容以文本形式返回给用户
"""

from __future__ import annotations

import os
import traceback

from logger import log
from server.types import ToolResult, ToolContext


def _is_bot_platform() -> bool:
    """判断当前是否运行在 Bot 平台（Lark/Discord/QQ）上。"""
    try:
        from user import get_current_interface
        interface = get_current_interface()
        if interface is None:
            from config import get_config
            cfg = get_config()
            interface = cfg.get('interface', 'cli')
        return interface in ('lark', 'discord', 'qq')
    except Exception:
        return False


def _read_file_content(file_path: str, ctx: ToolContext) -> str:
    """读取文件内容并返回文本，限制逻辑与 read_file 工具统一。

    从 ctx.cfg 读取 read_max_size_kb 和 read_max_lines 进行限制，
    超过限制时抛出异常（由调用方捕获并转为提示信息）。
    """
    file_size = os.path.getsize(file_path)
    file_size_kb = file_size / 1024
    max_size_kb = ctx.cfg.get('read_max_size_kb', 100)
    max_lines = ctx.cfg.get('read_max_lines', 1000)

    # 体积限制（与 read_file 一致：超过即拒绝）
    max_size_bytes = max_size_kb * 1024
    if file_size > max_size_bytes:
        raise FileTooLargeError(
            f'File too large: {file_path} ({file_size_kb:.1f} KB, '
            f'current size limit: {max_size_kb} KB), '
            f'Consider using set_read_limits to increase the limits, '
            f'or use other methods to send the content'
        )

    # 读取文件
    with open(file_path, 'rb') as f:
        raw = f.read()

    # 尝试 UTF-8 解码
    try:
        content = raw.decode('utf-8')
    except UnicodeDecodeError:
        raise BinaryFileError(
            f'Binary file ({file_size_kb:.1f} KB), cannot display as text'
        )

    # 行数限制（与 read_file 一致：超过即拒绝）
    all_lines = content.splitlines()
    line_count = len(all_lines)
    if line_count > max_lines:
        raise FileTooLargeError(
            f'File too large: {file_path} ({line_count} lines, '
            f'current line limit: {max_lines}), '
            f'Consider using set_read_limits to increase the limits, '
            f'or use other methods to send the content'
        )

    return content


class FileTooLargeError(Exception):
    """文件超过读取限制。"""
    pass


class BinaryFileError(Exception):
    """无法以文本形式读取的二进制文件。"""
    pass


def send_file(args: dict, ctx: ToolContext) -> ToolResult:
    """send_file 工具处理器。"""
    file_path = args.get('file_path', '')
    caption = args.get('caption', '').strip()

    log_label = f'Send File: {file_path}'

    try:
        # 验证文件是否存在
        if not os.path.exists(file_path):
            return ToolResult(
                text=f'<File not found: {file_path}>\n'
                     f'<Consider using the absolute path of the file>',
                log_msg=log_label,
            )

        # 验证是否是文件（不是目录）
        if not os.path.isfile(file_path):
            return ToolResult(
                text=f'<Not a file: {file_path}>',
                log_msg=log_label,
            )

        file_name = os.path.basename(file_path)

        # Bot 平台：通过 user.send_file() 发送附件
        if _is_bot_platform():
            if ctx.user is None:
                return ToolResult(
                    text='<No user interface available to send files>',
                    log_msg=log_label,
                )

            if not hasattr(ctx.user, 'send_file'):
                return ToolResult(
                    text='<Current user interface does not support sending files>',
                    log_msg=log_label,
                )

            ctx.user.send_file(file_path, caption=caption)
            return ToolResult(
                text=f'<Sent File: {file_name}>',
                log_msg=log_label,
            )

        # CLI/Headless 模式：读取文件内容通过 log_msg 回传给用户
        try:
            content = _read_file_content(file_path, ctx)
        except FileTooLargeError as e:
            return ToolResult(
                text=f'<{e}>',
                log_msg=log_label,
            )
        except BinaryFileError as e:
            return ToolResult(
                text=f'<{e}>',
                log_msg=log_label,
            )

        header = f'{file_name}'
        if caption:
            header += f': {caption} '

        return ToolResult(
            text=f'<Sent File: {file_name} (content displayed to user)>',
            log_msg=content,
            panel=True,
            panel_title=header,
        )

    except Exception as e:
        log(f'send_file error | {file_path}\n{traceback.format_exc()}')
        return ToolResult(
            text=f'<The following error occurred while sending the file: \n{type(e).__name__}: {e}\n'
                 f'Consider using the absolute path of the file>',
            log_msg=log_label,
        )

