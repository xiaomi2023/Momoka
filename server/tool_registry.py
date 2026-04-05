"""
server/tool_registry.py —— 工具注册中心。

负责收集各 Server 的工具定义，并根据条件动态生成可用工具列表。

使用方式：
    from server.tool_registry import get_available_tools
    
    # 获取所有可用工具
    tools = get_available_tools()
    
    # 或指定浏览器状态
    tools = get_available_tools(browser_open=True)

自动注册机制：
    启动时会自动扫描 server/servers/ 下的所有子模块，导入它们以触发注册。
    各模块只需在 __init__.py 中调用 register_server() 即可完成注册。
"""

from __future__ import annotations

import importlib
import pkgutil
from typing import Callable

import server.servers as servers_pkg
from server.servers import (
    get_available_tools as _get_auto_tools,
    get_registered_servers,
    get_server,
)


# ── 自动扫描注册 ───────────────────────────────────────────────────────────

def _auto_discover_servers() -> None:
    """自动发现并注册 server/servers/ 下的所有模块。
    
    遍历 server/servers/ 目录下的所有子包，导入它们以触发其中的 register_server() 调用。
    """
    package_path = servers_pkg.__path__
    
    for finder, name, ispkg in pkgutil.iter_modules(package_path):
        if not ispkg:
            continue  # 跳过非包文件
        
        try:
            # 导入模块，触发其中的 register_server() 调用
            importlib.import_module(f'server.servers.{name}')
        except ImportError:
            pass  # 导入失败则跳过


# 启动时自动发现
_auto_discover_servers()


# ── 公共 API ────────────────────────────────────────────────────────────────

def get_available_tools(browser_open: bool | None = None) -> list[dict]:
    """获取所有可用的工具列表。
    
    优先使用自动注册的工具，同时保持对浏览器特殊逻辑的支持。
    
    Args:
        browser_open: 浏览器是否已打开。如果为 None，则自动检测浏览器状态。
        
    Returns:
        可用的工具列表
    """
    # 获取自动注册的工具
    tools = _get_auto_tools()
    
    # 特殊处理浏览器页面工具（条件可用性）
    browser_reg = get_server('browser')
    if browser_reg is not None:
        # 如果浏览器未打开，需要过滤掉页面工具
        if browser_open is None:
            try:
                from server.servers.browser import is_browser_open
                browser_open = is_browser_open()
            except ImportError:
                browser_open = False
        
        # 获取浏览器基础工具名称集合
        base_tool_names = set()
        page_tool_names = set()
        
        try:
            from server.servers.browser.tooldef import (
                BROWSER_BASE_TOOLS, 
                BROWSER_PAGE_TOOLS
            )
            base_tool_names = {
                t['function']['name'] 
                for t in BROWSER_BASE_TOOLS 
                if 'function' in t and 'name' in t['function']
            }
            page_tool_names = {
                t['function']['name'] 
                for t in BROWSER_PAGE_TOOLS 
                if 'function' in t and 'name' in t['function']
            }
        except ImportError:
            pass
        
        # 如果浏览器未打开，过滤掉页面工具
        if not browser_open and page_tool_names:
            tools = [
                t for t in tools 
                if not (
                    'function' in t 
                    and t['function'].get('name') in page_tool_names
                    and t['function'].get('name') not in base_tool_names
                )
            ]
    
    return tools


def get_all_tool_names() -> list[str]:
    """获取所有可能的工具名称（用于调试或验证）。
    
    Returns:
        所有工具名称列表
    """
    from server.servers import get_all_tool_names as _get_names
    return _get_names()


def register_server_tools(
    module_path: str,
    tools_var_name: str = 'TOOL_DEFINITIONS',
    condition_func_name: str | None = None
) -> None:
    """（向后兼容）手动注册 server 工具。
    
    旧版注册方式，现已不推荐使用。新模块应直接在 __init__.py 中
    使用 server.servers.register_server() 进行注册。
    
    Args:
        module_path: 模块路径，如 'server.servers.my_module'
        tools_var_name: 工具定义变量名，默认为 'TOOL_DEFINITIONS'
        condition_func_name: 条件检查函数名，None 表示始终可用
        
    Example:
        # 旧方式（不推荐）
        register_server_tools('my_plugin.tools', 'MY_TOOLS', 'is_my_tools_available')
        
        # 新方式（推荐）
        # 在 server/servers/my_module/__init__.py 中：
        from server.servers import ServerRegistration, register_server
        register_server(ServerRegistration(...))
    """
    import importlib
    from server.servers import ServerRegistration, register_server
    
    module = importlib.import_module(module_path)
    tools = getattr(module, tools_var_name, [])
    
    condition = None
    if condition_func_name:
        condition = getattr(module, condition_func_name, None)
    
    # 从模块路径提取模块名
    name = module_path.split('.')[-1]
    
    def handler(tool_name: str, args: dict, ctx) -> ToolResult:
        # 旧版注册方式需要外部在 router.py 中处理路由
        # 这里返回一个提示，让 router.py 的特殊处理接管
        from server import ToolResult
        return ToolResult(text=f'__LEGACY_HANDLER__:{module_path}:{tool_name}')
    
    register_server(ServerRegistration(
        name=name,
        tool_definitions=list(tools),
        handler=handler,
        condition=condition,
    ))


def clear_cache() -> None:
    """（向后兼容）清除模块缓存，用于测试或热重载场景。
    
    现在也会清除自动注册表。
    """
    from server.servers import clear_registrations
    clear_registrations()
