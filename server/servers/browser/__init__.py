"""Browser server - 浏览器自动化工具。"""

from __future__ import annotations

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
