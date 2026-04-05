"""
server/router.py —— 工具调用调度路由。

职责：
  1. 将 tool_calls 分发到对应 handler
  2. 统一处理 user_log（handler 只填写 ToolResult.log_msg，不直接调用 user）
  3. 将结果写回 model 历史
  4. 管理文件折叠与 finish 后的全量折叠

路由机制：
  - 优先使用自动注册的 Server 模块（通过 server.servers.dispatch_tool）
  - 对浏览器工具保持特殊处理（因为需要传入 work_model）
"""

from __future__ import annotations

import json

from config import get_config
from logger import log
from server import ToolResult, ToolContext
from server.servers import dispatch_tool


# ── 路由 ──────────────────────────────────────────────────────────────────

def _execute_tool(name: str, args: dict, ctx: ToolContext,
                  work_model=None) -> ToolResult:
    """执行工具 —— 自动分发到注册的 Server。
    
    优先使用自动注册机制分发，对浏览器工具保持特殊处理。
    
    Args:
        name: 工具名称
        args: 工具参数
        ctx: 执行上下文
        work_model: 工作模型（浏览器工具需要）
        
    Returns:
        ToolResult: 执行结果
    """
    # 浏览器工具特殊处理（需要传入 work_model）
    if name.startswith('browse_'):
        from server.servers import browser as browser_handler
        return browser_handler.dispatch(name, args, ctx, work_model=work_model)
    
    # 尝试自动分发到已注册的 Server
    result = dispatch_tool(name, args, ctx)
    if result is not None:
        return result
    
    # 未知工具
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

    Args:
        work_model: 工作模型实例
        tool_calls: 工具调用列表
        user: 用户交互对象
        input_func: 输入函数
        
    Returns:
        (is_finish, all_file_contents)
        - is_finish: 是否调用了 finish 工具
        - all_file_contents: 所有文件内容字典
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
