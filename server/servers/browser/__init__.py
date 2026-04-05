"""
server/servers/browser/__init__.py —— Browser 模块自动注册。

涵盖所有 browse_* 工具：
  - 基础工具（始终可用）: browse_open, browse_search
  - 页面工具（浏览器打开后可用）: browse_read, browse_click, browse_fill, etc.

浏览器工具通过 router.py 特殊处理，因为 browse_read 需要传入 work_model 进行历史去重。
"""

from __future__ import annotations

from server import ToolResult, ToolContext
from server.servers import ServerRegistration, register_server
from server.servers.browser.tooldef import (
    BROWSER_BASE_TOOLS,
    BROWSER_PAGE_TOOLS,
    is_browser_page_available,
)
from server.servers.browser.browser import (
    dispatch,
    is_browser_open,
    browser_open,
    browser_read,
    browser_click,
    browser_fill,
    browser_press,
    browser_find,
    browser_pdf,
    browser_eval,
    browser_wait_for_navigation,
    browser_search,
    browser_switch,
    browser_hover,
    browser_select,
    browser_get_url,
    browser_scroll,
    browser_upload,
    browser_download,
    browser_close,
)


def _handle(name: str, args: dict, ctx: ToolContext) -> ToolResult:
    """浏览器工具处理函数。
    
    注意：浏览器工具实际上由 router.py 直接调用 browser.dispatch() 处理，
    因为 browse_read 需要传入 work_model 参数进行历史去重。
    这里的 _handle 仅作为备用，不会被正常调用。
    """
    # 浏览器工具由 router.py 特殊处理
    return dispatch(name, args, ctx)


# 导出公共接口
__all__ = [
    'dispatch',
    'is_browser_open',
    'browser_open',
    'browser_read',
    'browser_click',
    'browser_fill',
    'browser_press',
    'browser_find',
    'browser_pdf',
    'browser_eval',
    'browser_wait_for_navigation',
    'browser_search',
    'browser_switch',
    'browser_hover',
    'browser_select',
    'browser_get_url',
    'browser_scroll',
    'browser_upload',
    'browser_download',
    'browser_close',
]


# 注册浏览器模块（基础工具始终可用）
# 注意：页面工具的条件可用性由 tool_registry.py 特殊处理
register_server(ServerRegistration(
    name='browser',
    tool_definitions=BROWSER_BASE_TOOLS + BROWSER_PAGE_TOOLS,
    handler=_handle,
    condition=None,  # 基础工具始终可用，页面工具由 tool_registry 特殊过滤
))
