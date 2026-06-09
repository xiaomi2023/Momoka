"""
server/servers/browser/browser_state.py —— 浏览器状态管理。

使用 rebrowser-playwright 异步 API，通过独立后台线程事件循环运行，
对外暴露同步接口。

包含：
- 浏览器/页面单例管理
- 标签页切换与状态查询
- 浏览器关闭
"""

from __future__ import annotations

import asyncio
import time
import threading
from typing import Optional

from rebrowser_playwright.async_api import async_playwright, Page, Browser, Playwright

from logger import log
from server.servers.browser.util import (
    _CONTEXT_ERR,
    _USER_AGENT,
    _LAUNCH_ARGS,
)


# ── 全局单例（仅用于状态查询，实际对象在后台线程中） ─────────────────
_browser: Optional["Browser"] = None
_page: Optional["Page"] = None
_pw: Optional["Playwright"] = None

# UUID → 元素元数据映射（每次 browse_read 后重建）
_item_map: dict[str, dict] = {}

# ── 后台事件循环管理 ───────────────────────────────────────────────────
_loop: Optional[asyncio.AbstractEventLoop] = None
_loop_thread: Optional[threading.Thread] = None
_loop_lock = threading.Lock()


def _get_loop() -> asyncio.AbstractEventLoop:
    """获取或创建后台事件循环（线程安全）。"""
    global _loop, _loop_thread
    with _loop_lock:
        if _loop is None or _loop.is_closed():
            _loop = asyncio.new_event_loop()
            _loop_thread = threading.Thread(
                target=_loop.run_forever,
                daemon=True,
                name='playwright-loop'
            )
            _loop_thread.start()
            log("browser | Playwright background event loop started")
        return _loop


def _run_async(coro) -> any:
    """在后台事件循环中运行协程，同步等待结果。"""
    loop = _get_loop()
    future = asyncio.run_coroutine_threadsafe(coro, loop)
    return future.result(timeout=60)  # 60秒超时


# ── 浏览器状态查询 ─────────────────────────────────────────────────────

def get_browser_state() -> tuple[Optional[Playwright], Optional[Browser], Optional[Page]]:
    """获取当前浏览器状态。"""
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


def is_browser_open() -> bool:
    """检查浏览器是否已打开且页面可用。"""
    return _page is not None and not _page.is_closed()


# ── 异步核心操作 ───────────────────────────────────────────────────────

async def _async_ensure_browser(headless: bool = True) -> "Page":
    """异步确保浏览器和页面实例存在，返回当前 Page。"""
    global _pw, _browser, _page

    if _page is None or _page.is_closed():
        if _browser is None or not _browser.is_connected():
            if _pw is None:
                _pw = await async_playwright().start()
            _browser = await _pw.chromium.launch(headless=headless, args=_LAUNCH_ARGS)
        _page = await _browser.new_page(user_agent=_USER_AGENT)
        log("browser | New browser page created [rebrowser-playwright]")

        # 等待页面初始加载
        try:
            await _page.wait_for_load_state("domcontentloaded", timeout=5000)
        except Exception:
            pass
        # 探测 JS context 是否就绪
        for attempt in range(3):
            try:
                await _page.evaluate("1")
                break
            except Exception as e:
                if _CONTEXT_ERR in str(e) and attempt < 2:
                    await asyncio.sleep(0.3 * (attempt + 1))
                else:
                    break

    return _page


async def _async_maybe_switch_to_new_tab() -> None:
    """如果出现了新标签页，自动切换到最新的那个。"""
    global _page
    try:
        if _browser and _browser.is_connected():
            contexts = _browser.contexts
            if contexts:
                pages = contexts[0].pages
                if len(pages) > 1:
                    latest = pages[-1]
                    if latest != _page and not latest.is_closed():
                        old_url = _page.url
                        _page = latest
                        await _page.bring_to_front()
                        log(f"browser | New tab detected, auto-switched: {old_url} → {_page.url}")
    except Exception as e:
        log(f"browser | New tab detection failed: {e}")


async def _async_get_tabs_info() -> str:
    """获取所有标签页的信息字符串。"""
    try:
        if _browser and _browser.is_connected():
            contexts = _browser.contexts
            if contexts:
                pages = contexts[0].pages
                if not pages:
                    return ""
                lines = []
                for i, p in enumerate(pages):
                    marker = " ◀ Current" if p == _page else ""
                    try:
                        title = await p.title() or "(Untitled)"
                    except Exception:
                        title = "(unavailable)"
                    lines.append(f"  [{i}] {title}  {p.url}{marker}")
                return "<Tab list>\n" + "\n".join(lines) + "\n</Tab list>"
        return ""
    except Exception:
        return ""


async def _async_close() -> str:
    """异步关闭浏览器。"""
    global _pw, _browser, _page, _item_map

    if _page is None and _browser is None:
        return "<Browser is not open>"

    try:
        if _browser and _browser.is_connected():
            await _browser.close()
            log("browser | Browser closed")
        _pw = None
        _browser = None
        _page = None
        _item_map = {}
        return "<Browser closed successfully>"
    except Exception as e:
        log(f"browser | CLOSE error: {e}")
        return f"<Failed to close browser: {e}>"


# ── 同步包装接口（供外部调用） ─────────────────────────────────────────

def _ensure_browser(headless: bool = True) -> "Page":
    """同步包装：确保浏览器和页面实例存在。"""
    return _run_async(_async_ensure_browser(headless))


def _maybe_switch_to_new_tab() -> None:
    """同步包装：自动切换到新标签页。"""
    _run_async(_async_maybe_switch_to_new_tab())


def _get_tabs_info() -> str:
    """同步包装：获取标签页信息。"""
    return _run_async(_async_get_tabs_info())


def browser_close() -> str:
    """同步包装：关闭浏览器。"""
    return _run_async(_async_close())


# ── 导出异步函数（供 browser.py 中的异步实现直接调用） ────────────────
__all__ = [
    'get_browser_state',
    'get_browser',
    'get_page',
    'set_page',
    'get_item_map',
    'set_item_map',
    'is_browser_open',
    'browser_close',
    '_ensure_browser',
    '_maybe_switch_to_new_tab',
    '_get_tabs_info',
    '_run_async',
    '_async_ensure_browser',
    '_async_maybe_switch_to_new_tab',
    '_async_get_tabs_info',
    '_async_close',
]
