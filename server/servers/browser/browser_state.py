"""
server/servers/browser/browser_state.py —— 浏览器状态管理。

包含：
- 浏览器/页面单例管理
- 标签页切换与状态查询
- 浏览器关闭
"""

from __future__ import annotations

import time
from typing import Optional

from rebrowser_playwright.sync_api import sync_playwright, Page, Browser, Playwright

from logger import log
from server.servers.browser.util import (
    _CONTEXT_ERR,
    _USER_AGENT,
    _LAUNCH_ARGS,
)


# ── 全局单例 ──────────────────────────────────────────────────────────────
_pw: Optional["Playwright"] = None
_browser: Optional["Browser"] = None
_page: Optional["Page"] = None

# UUID → 元素元数据映射（每次 browse_read 后重建）
_item_map: dict[str, dict] = {}


def get_browser_state() -> tuple[Optional[Playwright], Optional[Browser], Optional[Page]]:
    """获取当前浏览器状态（供外部查询使用）。"""
    return _pw, _browser, _page


def get_browser() -> Optional[Browser]:
    """获取当前浏览器实例。"""
    return _browser


def get_page() -> Optional[Page]:
    """获取当前页面对象。"""
    return _page


def set_page(page: Page) -> None:
    """设置当前页面对象。"""
    global _page
    _page = page


def get_item_map() -> dict[str, dict]:
    """获取当前 UUID 元素映射。"""
    return _item_map


def set_item_map(new_map: dict[str, dict]) -> None:
    """更新 UUID 元素映射。"""
    global _item_map
    _item_map = new_map


def _ensure_browser(headless: bool = True) -> "Page":
    """确保浏览器和页面实例存在，返回当前 Page。"""
    global _pw, _browser, _page

    if _page is None or _page.is_closed():
        if _browser is None or not _browser.is_connected():
            if _pw is None:
                _pw = sync_playwright().start()
            _browser = _pw.chromium.launch(headless=headless, args=_LAUNCH_ARGS)
        _page = _browser.new_page(user_agent=_USER_AGENT)
        log("browser | New browser page created [rebrowser-playwright]")

        # 等待 rebrowser 反检测脚本注入完成，确保 JS context 稳定
        try:
            _page.wait_for_load_state("domcontentloaded", timeout=5000)
        except Exception:
            pass  # 新页面通常已加载，超时无妨
        # 用简单 evaluate 探测 context 是否就绪，带短延迟重试
        for attempt in range(3):
            try:
                _page.evaluate("1")  # 最小化探测
                break
            except Exception as e:
                if _CONTEXT_ERR in str(e) and attempt < 2:
                    time.sleep(0.3 * (attempt + 1))
                else:
                    break  # 非 context 错误或已达上限

    return _page


def _maybe_switch_to_new_tab() -> None:
    """如果出现了新标签页，自动切换到最新的那个。"""
    global _page
    try:
        pages = _browser.contexts[0].pages if _browser and _browser.is_connected() else []
        if len(pages) > 1:
            latest = pages[-1]
            if latest != _page and not latest.is_closed():
                old_url = _page.url
                _page = latest
                _page.bring_to_front()
                log(f"browser | New tab detected, auto-switched: {old_url} → {_page.url}")
    except Exception as e:
        log(f"browser | New tab detection failed: {e}")


def _get_tabs_info() -> str:
    """获取所有标签页的信息字符串。"""
    try:
        pages = _browser.contexts[0].pages if _browser and _browser.is_connected() else []
        if not pages:
            return ""
        lines = []
        for i, p in enumerate(pages):
            marker = " ◀ Current" if p == _page else ""
            try:
                title = p.title() or "(Untitled)"
            except Exception:
                title = "(unavailable)"
            lines.append(f"  [{i}] {title}  {p.url}{marker}")
        return "<Tab list>\n" + "\n".join(lines) + "\n</Tab list>"
    except Exception:
        return ""


def is_browser_open() -> bool:
    """检查浏览器是否已打开且页面可用。"""
    return _page is not None and not _page.is_closed()


def browser_close() -> str:
    """关闭浏览器，返回状态信息。"""
    global _pw, _browser, _page, _item_map

    if _page is None and _browser is None:
        return "<Browser is not open>"

    try:
        if _browser and _browser.is_connected():
            _browser.close()
            log("browser | Browser closed")
        _pw = None
        _browser = None
        _page = None
        _item_map = {}
        return "<Browser closed successfully>"
    except Exception as e:
        log(f"browser | CLOSE error: {e}")
        return f"<Failed to close browser: {e}>"
