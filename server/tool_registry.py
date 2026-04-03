"""
server/tool_registry.py —— 工具注册中心。

负责收集各 Server 的工具定义，并根据条件动态生成可用工具列表。

使用方式：
    from server.tool_registry import get_available_tools
    
    # 获取所有可用工具
    tools = get_available_tools()
    
    # 或指定浏览器状态
    tools = get_available_tools(browser_open=True)
"""

from __future__ import annotations

from typing import Callable


# ── Server 模块注册表 ───────────────────────────────────────────────────────
# 每个条目: (模块路径, 工具定义变量名, 条件检查函数名)
# 条件检查函数返回 bool，表示该组工具是否可用

_SERVER_REGISTRATIONS: list[tuple[str, str, str | None]] = [
    # (模块路径, 工具定义变量名, 条件检查函数名)
    ('server.servers.system_tooldef', 'TOOL_DEFINITIONS', None),
    ('server.servers.ask_user_tooldef', 'TOOL_DEFINITIONS', None),
    ('server.servers.office_tooldef', 'TOOL_DEFINITIONS', None),
    ('server.servers.settings_tooldef', 'TOOL_DEFINITIONS', None),
    ('server.servers.skill_tooldef', 'TOOL_DEFINITIONS', None),
    # 浏览器工具有两组，分别注册
    ('server.servers.browser_tooldef', 'BROWSER_BASE_TOOLS', None),
    ('server.servers.browser_tooldef', 'BROWSER_PAGE_TOOLS', 'is_browser_page_available'),
]


# ── 缓存 ───────────────────────────────────────────────────────────────────

_cached_modules: dict[str, object] = {}


def _get_module(module_path: str) -> object:
    """获取模块，带缓存。"""
    if module_path not in _cached_modules:
        import importlib
        _cached_modules[module_path] = importlib.import_module(module_path)
    return _cached_modules[module_path]


def _check_condition(module_path: str, condition_func_name: str | None) -> bool:
    """检查条件函数，如果没有条件函数则返回 True。"""
    if condition_func_name is None:
        return True
    module = _get_module(module_path)
    condition_func = getattr(module, condition_func_name, None)
    if condition_func is None:
        return True
    if callable(condition_func):
        return condition_func()
    return bool(condition_func)


def _get_tools_from_module(module_path: str, tools_var_name: str) -> list[dict]:
    """从模块获取工具定义列表。"""
    module = _get_module(module_path)
    tools = getattr(module, tools_var_name, None)
    if tools is None:
        return []
    return list(tools)


# ── 公共 API ────────────────────────────────────────────────────────────────

def get_available_tools(browser_open: bool | None = None) -> list[dict]:
    """获取所有可用的工具列表。
    
    Args:
        browser_open: 浏览器是否已打开。如果为 None，则自动检测浏览器状态。
        
    Returns:
        可用的工具列表
    """
    all_tools: list[dict] = []
    
    # 如果未指定浏览器状态，自动检测
    if browser_open is None:
        try:
            from server.servers.browser import is_browser_open
            browser_open = is_browser_open()
        except ImportError:
            browser_open = False
    
    for module_path, tools_var_name, condition_func_name in _SERVER_REGISTRATIONS:
        # 特殊处理浏览器页面工具的条件
        if condition_func_name == 'is_browser_page_available':
            if not browser_open:
                continue
        elif not _check_condition(module_path, condition_func_name):
            continue
        
        tools = _get_tools_from_module(module_path, tools_var_name)
        all_tools.extend(tools)
    
    return all_tools


def get_all_tool_names() -> list[str]:
    """获取所有可能的工具名称（用于调试或验证）。
    
    Returns:
        所有工具名称列表
    """
    names: list[str] = []
    for module_path, tools_var_name, _ in _SERVER_REGISTRATIONS:
        tools = _get_tools_from_module(module_path, tools_var_name)
        for tool in tools:
            if 'function' in tool and 'name' in tool['function']:
                names.append(tool['function']['name'])
    return names


def register_server_tools(
    module_path: str,
    tools_var_name: str = 'TOOL_DEFINITIONS',
    condition_func_name: str | None = None
) -> None:
    """注册新的 server 工具。
    
    Args:
        module_path: 模块路径，如 'server.servers.my_server_tooldef'
        tools_var_name: 工具定义变量名，默认为 'TOOL_DEFINITIONS'
        condition_func_name: 条件检查函数名，None 表示始终可用
        
    Example:
        register_server_tools('my_plugin.tools', 'MY_TOOLS', 'is_my_tools_available')
    """
    _SERVER_REGISTRATIONS.append((module_path, tools_var_name, condition_func_name))
    # 清除缓存以确保新模块被加载
    if module_path in _cached_modules:
        del _cached_modules[module_path]


def clear_cache() -> None:
    """清除模块缓存，用于测试或热重载场景。"""
    _cached_modules.clear()
