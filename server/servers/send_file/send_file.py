"""
server/servers/send_file/send_file.py — Send File tool handler.

send_file 工具处理器：将文件发送给用户（支持 Discord/Lark）。
"""

from __future__ import annotations

import os
import traceback

from logger import log
from server.types import ToolResult, ToolContext


def send_file(args: dict, ctx: ToolContext) -> ToolResult:
    """send_file 工具处理器：将文件发送给用户（支持 Discord/Lark/QQ）。"""
    file_path = args.get('file_path', '')
    caption = args.get('caption', '').strip()

    log_label = f'Send File: {file_path}'

    try:
        # 验证文件是否存在
        if not os.path.exists(file_path):
            return ToolResult(
                text=f'<File not found: {file_path}>\n'
                     f'Consider using the absolute path of the file.',
                log_msg=log_label,
            )

        # 验证是否是文件（不是目录）
        if not os.path.isfile(file_path):
            return ToolResult(
                text=f'<Not a file: {file_path}>',
                log_msg=log_label,
            )

        # 获取文件大小
        file_size = os.path.getsize(file_path)
        file_size_kb = file_size / 1024

        # 检查当前 user 是否支持 send_file 方法
        if ctx.user is None:
            return ToolResult(
                text='<No user interface available to send files.>',
                log_msg=log_label,
            )

        # 检查 user 对象是否有 send_file 方法
        if not hasattr(ctx.user, 'send_file'):
            return ToolResult(
                text='<Current user interface does not support sending files. '
                     'This feature is only available in Lark, Discord, or QQ mode.>',
                log_msg=log_label,
            )

        # 通过 user 接口发送文件
        ctx.user.send_file(file_path, caption=caption)

        file_name = os.path.basename(file_path)

        return ToolResult(
            text=f'<Sent File: {file_name}>',
            log_msg=f'{log_label}',
        )

    except Exception as e:
        log(f'send_file error | {file_path}\n{traceback.format_exc()}')
        return ToolResult(
            text=f'<The following error occurred while sending the file: \n{type(e).__name__}: {e}\n'
                 f'Consider using the absolute path of the file>',
            log_msg=log_label,
        )
