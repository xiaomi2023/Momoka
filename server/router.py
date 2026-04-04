"""
server/router.py —— 工具调用调度路由。

职责：
  1. 将 tool_calls 分发到对应 handler
  2. 统一处理 user_log（handler 只填写 ToolResult.log_msg，不直接调用 user）
  3. 将结果写回 model 历史
  4. 管理文件折叠与 finish 后的全量折叠

具体执行实现分布在：
  server/servers/settings/settings.py  —— set_wait / set_read_limits
  server/servers/skill/skill.py        —— get_skill
  server/servers/system/system.py      —— system_command / change_directory / ask_user / finish
                                         read_file / edit_file / replace_file / read_sheet
  server/servers/browser/browser.py    —— 所有 browse_* 工具
"""

from __future__ import annotations

import json

from config import get_config
from logger import log
from server import ToolResult, ToolContext
from server.servers import system as system_handler
from server.servers import user as user_handler
from server.servers import browser as browser_handler
from server.servers import settings, skill


# ── 路由 ──────────────────────────────────────────────────────────────────

def _execute_tool(name: str, args: dict, ctx: ToolContext,
                  work_model=None) -> ToolResult:
    match name:
        case 'finish':           return system_handler.finish(args, ctx)
        case 'system_command':   return system_handler.system_command(args, ctx)
        case 'change_directory': return system_handler.change_directory(args, ctx)
        case 'ask_user':         return user_handler.ask_user(args, ctx)
        case 'set_todolist':     return user_handler.set_todolist(args, ctx)
        case 'ask_option':       return user_handler.ask_option(args, ctx)

        case 'edit_file':        return system_handler.edit_file_tool(args, ctx)
        case 'replace_file':     return system_handler.replace_file(args, ctx)
        case 'read_file':        return system_handler.read_file(args, ctx)
        case 'read_sheet':       return system_handler.read_sheet(args, ctx)

        case 'get_skill':        return skill.get_skill(args, ctx)

        case 'set_wait':         return settings.set_wait(args, ctx)
        case 'set_read_limits':  return settings.set_read_limits(args, ctx)

        case _ if name.startswith('browse_'):
            return browser_handler.dispatch(name, args, ctx, work_model=work_model)

        case _:
            return ToolResult(text=f'未知工具: {name}')


# ── user_log 统一输出 ─────────────────────────────────────────────────────

def _emit_logs(result: ToolResult, user) -> None:
    """根据 ToolResult.log_msg 向 user 输出日志。"""
    if user is None or result.log_msg is None:
        return
    if isinstance(result.log_msg, list):
        for msg, role in result.log_msg:
            user.user_log(msg, role=role)
    else:
        user.user_log(result.log_msg, role=result.log_role)


# ── 主入口 ────────────────────────────────────────────────────────────────

def execute_tool_calls(
        work_model,
        tool_calls: list,
        user=None,
        input_func=input,
) -> tuple[bool, dict[str, str]]:
    """依次执行 tool_calls，将结果写回 model 历史。

    Returns:
        (is_finish, all_file_contents)
    """
    cfg = get_config()
    ctx = ToolContext(cfg=cfg, input_func=input_func)

    all_file_contents: dict[str, str] = {}
    is_finish = False

    for tc in tool_calls:
        name = tc.function.name
        try:
            args = json.loads(tc.function.arguments)
        except json.JSONDecodeError:
            args = {}

        result = _execute_tool(name, args, ctx, work_model=work_model)

        _emit_logs(result, user)

        log(f'execute_tool_calls | {name}({args}) → {result.text}')
        work_model.add_tool_result(
            tc.id, result.text,
            file_contents=result.file_contents if result.file_contents else None,
        )

        if result.file_contents:
            all_file_contents.update(result.file_contents)
            for file_key in result.file_contents:
                collapsed = work_model.collapse_file_in_history(file_key)
                if collapsed:
                    log(f'execute_tool_calls | 折叠历史 [{name}]: {file_key} ({collapsed} 条)')

        if result.is_finish:
            is_finish = True
            break

    if is_finish:
        _collapse_all_files(work_model)

    return is_finish, all_file_contents


def _collapse_all_files(work_model) -> None:
    """折叠历史中所有已打开的文件和浏览器网页内容。"""
    all_file_keys = set()
    for meta in work_model._meta:
        if 'file_contents' in meta:
            all_file_keys.update(meta['file_contents'].keys())
    for file_key in all_file_keys:
        collapsed = work_model.collapse_file_in_history(file_key)
        if collapsed:
            log(f'_collapse_all_files | 折叠: {file_key} ({collapsed} 条)')
