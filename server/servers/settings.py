"""
server/servers/settings.py —— set_wait / set_read_limits 处理器。
"""

from __future__ import annotations

from server import ToolResult, ToolContext


def set_wait(args: dict, ctx: ToolContext) -> ToolResult:
    from config import set_wait as _set_wait, set_wait_download
    seconds = int(args.get('seconds', 10))
    target = args.get('target', 'default')

    if target == 'download':
        set_wait_download(seconds)
        msg = f'Browser download timeout set to: {seconds}s'
        return ToolResult(
            text=f'浏览器下载超时时长已更新为 {seconds} 秒',
            log_msg=msg,
            log_role='SETTINGS',
        )
    else:
        _set_wait(seconds)
        msg = f'Timeout set to: {seconds}s'
        return ToolResult(
            text=f'超时时长已更新为 {seconds} 秒',
            log_msg=msg,
            log_role='SETTINGS',
        )


def set_read_limits(args: dict, ctx: ToolContext) -> ToolResult:
    from config import set_read_limits as _set_read_limits
    MAX_LINES = 50000
    MAX_SIZE_KB = 5120

    raw_lines = args.get('max_lines')
    raw_size = args.get('max_size_kb')
    max_lines = min(int(raw_lines), MAX_LINES) if raw_lines is not None else None
    max_size_kb = min(int(raw_size), MAX_SIZE_KB) if raw_size is not None else None
    _set_read_limits(max_lines=max_lines, max_size_kb=max_size_kb)

    parts = []
    if max_lines is not None:
        clamped = raw_lines != max_lines
        parts.append(f'Max lines: {max_lines}' + (' (clamped to limit)' if clamped else ''))
    if max_size_kb is not None:
        clamped = raw_size != max_size_kb
        parts.append(f'Max size: {max_size_kb} KB' + (' (clamped to limit)' if clamped else ''))

    msg = 'File read limits updated → ' + ', '.join(parts) if parts else 'No changes made'
    return ToolResult(text=msg, log_msg=msg, log_role='SETTINGS')