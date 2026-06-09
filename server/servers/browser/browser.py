"""
server/servers/browser/browser.py —— 浏览器工具处理器。

所有 browse_* 工具统一由 dispatch() 入口分发，
所有浏览器操作通过 browser_state 的后台事件循环使用异步 API 执行。

基于 rebrowser-playwright 异步 API 的浏览器操作模块（无障碍树版）。

支持的操作：
    BROWSE_OPEN                  打开网页
    BROWSE_READ                  读取页面内容（支持三种模式）
    BROWSE_CLICK                 点击可交互元素（通过 UUID）
    BROWSE_FILL                  向 textbox/input 填充文字（通过 UUID）
    BROWSE_HOVER                 悬停元素，触发 hover 事件（展开菜单等）
    BROWSE_SELECT                在原生 <select> 下拉框中选择选项
    BROWSE_PRESS                 向元素发送真实按键
    BROWSE_EVAL                  执行 JavaScript
    BROWSE_CLOSE                 关闭浏览器
    BROWSE_FIND                  在页面中搜索文字，返回匹配元素信息
    BROWSE_PDF                   将当前页面打印为 PDF 并保存
    BROWSE_GET_URL               获取当前页面 URL 和标题
    BROWSE_SCROLL                滚动页面或指定元素
    BROWSE_UPLOAD                向文件选择框上传本地文件
    BROWSE_DOWNLOAD              点击下载链接并将文件保存到本地
    BROWSE_WAIT_FOR_NAVIGATION   等待页面导航完成
    BROWSE_SEARCH                使用搜索引擎搜索
    BROWSE_SWITCH                切换标签页

读取模式（browse_read 的 mode 参数）：
    "interactive"  — 只显示可交互元素列表（含 UUID、类型、标签文字）
    "text"         — 只显示页面正文（无障碍树文字节点，过滤空白）
    "all"          — 同时显示正文与可交互元素（默认）

交互元素由 UUID 标识：
    每次调用 browse_read 后 UUID 映射会刷新。
    browse_click / browse_fill 只需传入 UUID，无需选择器或坐标。
"""

from __future__ import annotations

import asyncio
import base64
import os
import time
from urllib.parse import quote_plus

from logger import log
from server.types import ToolResult, ToolContext
from server.servers.browser.util import (
    _load_js,
    _async_safe_evaluate,
    _timeout_ms,
    SEARCH_ENGINES,
)
from server.servers.browser.browser_state import (
    get_page,
    get_item_map,
    set_item_map,
    _ensure_browser,
    _maybe_switch_to_new_tab,
    _get_tabs_info,
    is_browser_open,
    browser_close,
    _run_async,
    _async_ensure_browser,
    _async_maybe_switch_to_new_tab,
    _async_get_tabs_info,
)
from server.servers.browser.accessibility import (
    _parse_ax_tree,
    _resolve_element,
    _refresh_item_map,
    _async_parse_ax_tree,
    _async_resolve_element,
    _async_refresh_item_map,
)


# ── 页面内容缓存（用于 browse_read 历史去重） ─────────────────────────

_browse_read_cache: dict[str, str] = {}
"""缓存每个 URL 上次读取的页面内容，key 为当前页面 URL，value 为完整读取结果。
   若下次读取同一 URL 且内容未变化，则返回精简提示以节省 token。"""

# ── 异步核心操作函数 ─────────────────────────────────────────────────────

async def _async_browser_open(url: str, wait_until: str = "domcontentloaded") -> str:
    """异步：导航到指定 URL，返回页面标题。"""
    from server.servers.browser.browser_state import _async_ensure_browser
    page = await _async_ensure_browser()
    log(f"browser | OPEN {url}")
    try:
        await page.goto(url, wait_until=wait_until, timeout=_timeout_ms())
        try:
            await page.wait_for_load_state("networkidle", timeout=5000)
        except Exception:
            pass
        try:
            title = await _async_safe_evaluate(page, "() => document.title")
        except Exception:
            title = await page.title()
        return f"Open: {url}\nTitle: {title}"
    except Exception as e:
        log(f"browser | OPEN error: {e}")
        return f"<Failed to open Page: {e}>"


async def _async_browser_read(page, char_start: int = 0, char_end: int = 4000, mode: str = "all") -> str:
    """异步：读取当前页面内容。"""
    from server.servers.browser.browser_state import _async_maybe_switch_to_new_tab
    await _async_maybe_switch_to_new_tab()

    if page is None or page.is_closed():
        return "<The browser has not been opened yet>"

    if mode not in ("interactive", "text", "all"):
        mode = "all"

    text_lines, interactive_items = await _async_parse_ax_tree(page)

    set_item_map({item['uuid']: item for item in interactive_items})

    header = f"<Current: {page.url}>\n<Read mode: {mode}>\n"
    tabs_info = await _async_get_tabs_info()
    if tabs_info:
        header += tabs_info + "\n"

    sections: list[str] = []

    # 正文部分
    if mode in ("text", "all"):
        body = "\n".join(line for line in text_lines if line.strip())
        total_len = len(body)
        body = body[char_start:char_end]
        if total_len > char_end:
            body += (
                f"\n...(Truncated from char {char_start} to {char_end}, totaling {total_len} characters)\n"
                f"<You can adjust char_start and char_end parameters to read more>"
            )
        if body:
            sections.append("<Text>\n" + body + "\n</Text>")

    # 可交互元素部分
    if mode in ("interactive", "all"):
        if interactive_items:
            lines = ["<Interactive Items>"]
            for item in interactive_items:
                vis = '' if item.get('visible', True) else '  (hidden)'
                extra_info = ''
                if item.get('disabled'):
                    extra_info += '  [Disabled]'
                if item.get('fill'):
                    extra_info += f'  [Fill: {item["fill"]}]'
                if item.get('field_label'):
                    extra_info += f'  [Label: {item["field_label"]}]'
                if item.get('input_type'):
                    extra_info += f' (type={item["input_type"]})'
                if 'checked' in item:
                    extra_info += f'  [Checked: {item["checked"]}]'
                if item.get('state'):
                    extra_info += f'  [State: {item["state"]}]'
                lines.append(f"  [{item['uuid']}] {item['role']}  {item['name']}{vis}{extra_info}")
            lines.append("</Interactive Items>")
            sections.append("\n".join(lines))
        elif mode == "interactive":
            sections.append("<Interactive Items>(NULL)</Interactive Items>")

    log(f"browser | READ mode={mode} text_lines={len(text_lines)} interactive={len(interactive_items)}")
    return header + "\n".join(sections)


async def _async_browser_click(page, element_uuid: str) -> str:
    """异步：点击指定 UUID 对应的可交互元素。"""
    if page is None or page.is_closed():
        return "<The browser has not been opened yet>"

    item = get_item_map().get(element_uuid)
    if item is None:
        return f"<Failed to Click: ID {element_uuid!r} does not exist. Consider use browser_read(string=interactive)>"

    label = f"[{element_uuid}] {item['role']} \"{item['name']}\""
    handle = await _async_resolve_element(page, item)
    if handle is None:
        return f"<Failed to Click: Cannot locate element {label}>"

    try:
        await handle.click(timeout=_timeout_ms())
        log(f"browser | CLICK {label}")
        refresh_msg = await _async_refresh_item_map()
        return f"<Clicked: {label}\n{refresh_msg}>"
    except Exception as e:
        log(f"browser | CLICK error {label}: {e}")
        return f"<Failed to Click {label}: {e}>"


async def _async_browser_fill(page, element_uuid: str, text: str) -> str:
    """异步：向指定 UUID 对应的 textbox/searchbox/combobox 填充文字。"""
    if page is None or page.is_closed():
        return "<The browser has not been opened yet>"

    item = get_item_map().get(element_uuid)
    if item is None:
        return f"<Failed to Fill: ID {element_uuid!r} does not exist. Consider use browser_read(string=interactive)>"

    role = item['role']
    label = f"[{element_uuid}] {role} \"{item['name']}\""

    _fillable = {'textbox', 'searchbox', 'combobox', 'spinbutton'}
    if role not in _fillable:
        return (f"<Failed to Fill: Element {label} type is {role!r}. Text fill not supported>"
                f"<Supported types: {', '.join(sorted(_fillable))}>")

    handle = await _async_resolve_element(page, item)
    if handle is None:
        return f"<Failed to Fill: Cannot locate element {label}>"

    try:
        await handle.fill(text, timeout=_timeout_ms())
        log(f"browser | FILL {label} → {text!r}")
        refresh_msg = await _async_refresh_item_map()
        return f"<Filled element {label} with: {text!r}>\n{refresh_msg}"
    except Exception as e:
        log(f"browser | FILL error {label}: {e}")
        return f"<Failed to Fill {label}: {e}>"


async def _async_browser_press(page, element_uuid: str, key: str) -> str:
    """异步：向指定 UUID 元素发送真实按键。"""
    if page is None or page.is_closed():
        return "<The browser has not been opened yet>"

    item = get_item_map().get(element_uuid)
    if item is None:
        return f"<Failed to Press: ID {element_uuid!r} does not exist. Consider use browser_read(string=interactive)>"

    label = f"[{element_uuid}] {item['role']} \"{item['name']}\""
    handle = await _async_resolve_element(page, item)
    if handle is None:
        return f"<Failed to Press: Cannot locate element {label}>"

    try:
        await handle.press(key, timeout=_timeout_ms())
        log(f"browser | PRESS {label} key={key!r}")
        refresh_msg = await _async_refresh_item_map()
        return f"<Pressed key {key!r} on element {label}>\n{refresh_msg}"
    except Exception as e:
        log(f"browser | PRESS error {label}: {e}")
        return f"<Failed to Press {label}: {e}>"


async def _async_browser_eval(page, script: str) -> str:
    """异步：在当前页面执行 JavaScript。"""
    if page is None or page.is_closed():
        return "<The browser has not been opened yet>"
    try:
        result = await _async_safe_evaluate(page, script)
        try:
            await page.wait_for_load_state("networkidle", timeout=_timeout_ms())
        except Exception:
            pass
        log(f"browser | EVAL result: {result}")
        base_msg = f"JavaScript execution result: {result}"
        async_keywords = ['setTimeout', 'setInterval', 'Promise', 'async', 'await']
        if any(k in script for k in async_keywords):
            base_msg += "\n<Warning: Possible async operations detected, result may be incomplete>"
        return base_msg
    except Exception as e:
        log(f"browser | EVAL error: {e}")
        err_msg = f"JavaScript execution failed: {e}"
        if "return" in script:
            err_msg += "\n<Tip: Top-level return is not allowed. Use IIFE for multi-step logic: (() => { ...; return result; })()>"
        return err_msg


async def _async_browser_find(page, text: str, max_results: int = 10) -> str:
    """异步：在页面中搜索包含指定文字的可见元素。"""
    if page is None or page.is_closed():
        return "<The browser has not been opened yet>"
    try:
        results = await _async_safe_evaluate(
            page,
            _load_js('find_elements.js'),
            [text, max_results],
        )
        if not results:
            return f"<No visible elements containing {text!r} found on current page>"
        lines = [f"<Found {len(results)} elements containing {text!r} on the page:>"]
        for i, r in enumerate(results, 1):
            matched_uuid = next(
                (uid for uid, item in get_item_map().items() if text in item['name']),
                None
            )
            uuid_hint = (f"  → UUID: {matched_uuid}" if matched_uuid
                         else "  → No corresponding ID, consider calling browse_read before interacting")
            lines.append(
                f"  [{i}] <{r['tag']}> Selector: {r['selector']}\n"
                f"      Text: {r['snippet']}\n"
                f"{uuid_hint}"
            )
        log(f"browser | FIND {text!r} → {len(results)} results")
        return "\n".join(lines)
    except Exception as e:
        log(f"browser | FIND error: {e}")
        return f"<Page search failed: {e}>"


async def _async_browser_pdf(page, save_dir: str = ".") -> str:
    """异步：将当前页面打印为 PDF。"""
    if page is None or page.is_closed():
        return "<The browser has not been opened yet>"
    try:
        os.makedirs(save_dir, exist_ok=True)
        filename = os.path.join(save_dir, f"page_{int(time.time())}.pdf")

        cdp = await page.context.new_cdp_session(page)
        result = await cdp.send("Page.printToPDF", {
            "printBackground": True,
            "paperWidth": 8.27,
            "paperHeight": 11.69,
        })
        await cdp.detach()
        pdf_bytes = base64.b64decode(result["data"])
        with open(filename, "wb") as f:
            f.write(pdf_bytes)
        size = os.path.getsize(filename)
        log(f"browser | PDF saved to {filename} ({size} bytes)")
        return f"PDF has been saved at: {filename} ({size / 1024:.1f} KB)"
    except Exception as e:
        log(f"browser | PDF error: {e}")
        return f"Failed at generating PDF: {e}"


async def _async_browser_wait_for_navigation(page, timeout: int = None, state: str = "networkidle") -> str:
    """异步：等待页面导航完成。"""
    if page is None or page.is_closed():
        return "<The browser has not been opened yet>"
    try:
        timeout_ms = (timeout if timeout is not None else (_timeout_ms() // 1000)) * 1000
        await page.wait_for_load_state(state, timeout=timeout_ms)
        log(f"browser | WAIT completed: state={state}")
        return f"<Page load completed (state: {state})>"
    except Exception as e:
        log(f"browser | WAIT error: {e}")
        return f"<Failed to wait for page load: {e}>"


async def _async_browser_search(query: str, engine: str = 'google') -> str:
    """异步：使用指定搜索引擎搜索关键词。"""
    engine = engine.lower()
    base_url = SEARCH_ENGINES.get(engine)
    if base_url is None:
        return f"<Unsupported search engine: {engine!r}. Supported: {', '.join(SEARCH_ENGINES)}>"
    url = base_url + quote_plus(query)
    log(f"browser | SEARCH [{engine}] {query!r} → {url}")
    page = await _async_ensure_browser()
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=_timeout_ms())
        try:
            await page.wait_for_load_state("networkidle", timeout=5000)
        except Exception:
            pass
        try:
            title = await _async_safe_evaluate(page, "() => document.title")
        except Exception:
            title = await page.title()
        return f"<Opened page: {url}\nTitle: {title}>"
    except Exception as e:
        log(f"browser | SEARCH error: {e}")
        return f"<Search failed: {e}>"


async def _async_browser_hover(page, element_uuid: str) -> str:
    """异步：将鼠标悬停在指定 UUID 对应的元素上。"""
    if page is None or page.is_closed():
        return "<The browser has not been opened yet>"

    item = get_item_map().get(element_uuid)
    if item is None:
        return f"<Failed to Hover: ID {element_uuid!r} does not exist. Consider use browser_read(string=interactive)>"

    label = f"[{element_uuid}] {item['role']} \"{item['name']}\""
    handle = await _async_resolve_element(page, item)
    if handle is None:
        return f"<Failed to Hover: Cannot locate element {label}>"

    try:
        await handle.hover(timeout=_timeout_ms())
        log(f"browser | HOVER {label}")
        refresh_msg = await _async_refresh_item_map()
        return f"<Hovered over element: {label}>\n{refresh_msg}"
    except Exception as e:
        log(f"browser | HOVER error {label}: {e}")
        return f"<Failed to Hover {label}: {e}>"


async def _async_browser_select(page, element_uuid: str, value: str) -> str:
    """异步：在指定 UUID 对应的 <select> 下拉框中选择选项。"""
    if page is None or page.is_closed():
        return "<The browser has not been opened yet>"

    item = get_item_map().get(element_uuid)
    if item is None:
        return f"<Failed to Select: ID {element_uuid!r} does not exist. Consider use browser_read(string=interactive)>"

    label = f"[{element_uuid}] {item['role']} \"{item['name']}\""
    handle = await _async_resolve_element(page, item)
    if handle is None:
        return f"<Failed to Select: Cannot locate element {label}>"

    try:
        select_args: dict = {}
        if value.isdigit():
            select_args['index'] = int(value)
        else:
            select_args['label'] = value

        selected = await handle.select_option(**{k: v for k, v in select_args.items()},
                                               timeout=_timeout_ms())
        log(f"browser | SELECT {label} → {selected}")
        refresh_msg = await _async_refresh_item_map()
        return f"<Selected in {label}: {selected}>\n{refresh_msg}"
    except Exception:
        try:
            selected = await handle.select_option(value=value, timeout=_timeout_ms())
            log(f"browser | SELECT (value fallback) {label} → {selected}")
            refresh_msg = await _async_refresh_item_map()
            return f"<Selected in {label}: {selected}>\n{refresh_msg}"
        except Exception as e:
            log(f"browser | SELECT error {label}: {e}")
        return f"<Failed to Select {label}: {e}>"


async def _async_browser_get_url(page) -> str:
    """异步：返回当前页面的 URL 和标题。"""
    if page is None or page.is_closed():
        return "<The browser has not been opened yet>"
    try:
        url = page.url
        title = await page.title() or "(No title)"
        log(f"browser | GET_URL {url}")
        return f"<Current Page>\n  URL:   {url}\n  Title: {title}"
    except Exception as e:
        log(f"browser | GET_URL error: {e}")
        return f"<Failed to get URL: {e}>"


async def _async_browser_scroll(page, direction: str = "down", amount: int = 500,
                                 element_uuid: str | None = None) -> str:
    """异步：滚动页面或指定元素。"""
    if page is None or page.is_closed():
        return "<The browser has not been opened yet>"

    direction = direction.lower()
    _dir_map = {
        'down':  (0,       amount),
        'up':    (0,      -amount),
        'right': (amount,  0),
        'left':  (-amount, 0),
    }
    if direction not in _dir_map:
        return f"<Unsupported scroll direction: {direction!r}, please use up / down / left / right>"

    delta_x, delta_y = _dir_map[direction]

    try:
        if element_uuid:
            item = get_item_map().get(element_uuid)
            if item is None:
                return f"<Failed to Scroll: ID {element_uuid!r} does not exist, consider calling browse_read first>"
            handle = await _async_resolve_element(page, item)
            if handle is None:
                return f"<Failed to Scroll: Cannot locate element [{element_uuid}]>"
            await handle.evaluate(
                f"el => el.scrollBy({delta_x}, {delta_y})"
            )
            label = f"element [{element_uuid}] \"{item['name']}\""
        else:
            await _async_safe_evaluate(page, f"window.scrollBy({delta_x}, {delta_y})")
            label = "page"

        log(f"browser | SCROLL {label} {direction} {amount}px")
        refresh_msg = await _async_refresh_item_map()
        return f"<Scrolled {label} {direction} by {amount}px>\n{refresh_msg}"
    except Exception as e:
        log(f"browser | SCROLL error: {e}")
        return f"<Failed to Scroll: {e}>"


async def _async_browser_upload(page, element_uuid: str, file_paths: list[str] | str) -> str:
    """异步：向指定 UUID 对应的文件选择框上传文件。"""
    if page is None or page.is_closed():
        return "<The browser has not been opened yet>"

    if isinstance(file_paths, str):
        file_paths = [file_paths]

    missing = [p for p in file_paths if not os.path.isfile(p)]
    if missing:
        return f"<Upload failed: The following files does not exist:\n" + "\n".join(f"  {p}" for p in missing) + ">"

    item = get_item_map().get(element_uuid)
    if item is None:
        return f"<Failed to Upload: ID {element_uuid!r} does not exist. Consider use browser_read(string=interactive)>"

    label = f"[{element_uuid}] {item['role']} \"{item['name']}\""

    try:
        async with page.expect_file_chooser(timeout=_timeout_ms()) as fc_info:
            handle = await _async_resolve_element(page, item)
            if handle is None:
                return f"<Failed to Upload: Cannot locate element {label}>"
            await handle.click(timeout=_timeout_ms())
        await fc_info.value.set_files(file_paths)
        names = ", ".join(os.path.basename(p) for p in file_paths)
        log(f"browser | UPLOAD {label} ← {file_paths}")
        refresh_msg = await _async_refresh_item_map()
        return f"<Uploaded {len(file_paths)} file(s) to {label}: {names}>\n{refresh_msg}"
    except Exception as e:
        try:
            handle = await _async_resolve_element(page, item)
            if handle is None:
                return f"<Failed to Upload: Cannot locate element {label}: {e}>"
            await handle.set_input_files(file_paths, timeout=_timeout_ms())
            names = ", ".join(os.path.basename(p) for p in file_paths)
            log(f"browser | UPLOAD (set_input_files fallback) {label} ← {file_paths}")
            refresh_msg = await _async_refresh_item_map()
            return f"<Uploaded {len(file_paths)} file(s) to {label}: {names}>\n{refresh_msg}"
        except Exception as e2:
            log(f"browser | UPLOAD error {label}: {e2}")
            return f"<Failed to Upload {label}: {e2}>"


async def _async_browser_download(page, element_uuid: str, save_dir: str = ".") -> str:
    """异步：点击指定 UUID 对应的下载链接/按钮。"""
    if page is None or page.is_closed():
        return "<The browser has not been opened yet>"

    item = get_item_map().get(element_uuid)
    if item is None:
        return f"<Failed to Download: ID {element_uuid!r} does not exist. Consider use browser_read(string=interactive)>"

    label = f"[{element_uuid}] {item['role']} \"{item['name']}\""

    try:
        os.makedirs(save_dir, exist_ok=True)
        from config import get_config
        download_timeout_ms = get_config().get('wait_download', 60) * 1000
        async with page.expect_download(timeout=download_timeout_ms) as dl_info:
            handle = await _async_resolve_element(page, item)
            if handle is None:
                return f"<Failed to Download: Cannot locate element {label}>"
            await handle.click(timeout=_timeout_ms())
        download = dl_info.value
        suggested = download.suggested_filename or f"download_{int(time.time())}"
        save_path = os.path.join(save_dir, suggested)
        await download.save_as(save_path)
        size = os.path.getsize(save_path)
        log(f"browser | DOWNLOAD {label} → {save_path} ({size} bytes)")
        refresh_msg = await _async_refresh_item_map()
        return f"<Download completed: {save_path} ({size / 1024:.1f} KB)>\n{refresh_msg}"
    except Exception as e:
        log(f"browser | DOWNLOAD error {label}: {e}")
        return f"<Failed to Download {label}: {e}>"


# ── 同步包装函数（通过 _run_async 在后台线程中执行异步操作） ─────────

def browser_open(url: str, wait_until: str = "domcontentloaded") -> str:
    """导航到指定 URL，返回页面标题。"""
    return _run_async(_async_browser_open(url, wait_until))


def browser_read(char_start: int = 0, char_end: int = 4000, mode: str = "all") -> str:
    """读取当前页面内容。"""
    _maybe_switch_to_new_tab()
    page = get_page()
    if page is None or page.is_closed():
        return "<The browser has not been opened yet>"
    return _run_async(_async_browser_read(page, char_start, char_end, mode))


def browser_click(element_uuid: str) -> str:
    """点击指定 UUID 对应的可交互元素。"""
    page = get_page()
    return _run_async(_async_browser_click(page, element_uuid))


def browser_fill(element_uuid: str, text: str) -> str:
    """向指定 UUID 对应的 textbox / searchbox / combobox 填充文字。"""
    page = get_page()
    return _run_async(_async_browser_fill(page, element_uuid, text))


def browser_press(element_uuid: str, key: str) -> str:
    """向指定 UUID 元素发送真实按键。"""
    page = get_page()
    return _run_async(_async_browser_press(page, element_uuid, key))


def browser_eval(script: str) -> str:
    """在当前页面执行 JavaScript。"""
    page = get_page()
    return _run_async(_async_browser_eval(page, script))


def browser_find(text: str, max_results: int = 10) -> str:
    """在当前页面中搜索包含指定文字的可见元素。"""
    page = get_page()
    return _run_async(_async_browser_find(page, text, max_results))


def browser_pdf(save_dir: str = ".") -> str:
    """将当前页面打印为 PDF。"""
    page = get_page()
    return _run_async(_async_browser_pdf(page, save_dir))


def browser_wait_for_navigation(timeout: int = None, state: str = "networkidle") -> str:
    """等待页面导航完成。"""
    page = get_page()
    return _run_async(_async_browser_wait_for_navigation(page, timeout, state))


def browser_search(query: str, engine: str = 'google') -> str:
    """使用指定搜索引擎搜索关键词。"""
    return _run_async(_async_browser_search(query, engine))


def browser_hover(element_uuid: str) -> str:
    """将鼠标悬停在指定 UUID 对应的元素上。"""
    page = get_page()
    return _run_async(_async_browser_hover(page, element_uuid))


def browser_select(element_uuid: str, value: str) -> str:
    """在指定 UUID 对应的 <select> 下拉框中选择选项。"""
    page = get_page()
    return _run_async(_async_browser_select(page, element_uuid, value))


def browser_get_url() -> str:
    """返回当前页面的 URL 和标题。"""
    page = get_page()
    return _run_async(_async_browser_get_url(page))


def browser_scroll(direction: str = "down", amount: int = 500,
                   element_uuid: str | None = None) -> str:
    """滚动页面或指定元素。"""
    page = get_page()
    return _run_async(_async_browser_scroll(page, direction, amount, element_uuid))


def browser_upload(element_uuid: str, file_paths: list[str] | str) -> str:
    """向指定 UUID 对应的文件选择框上传文件。"""
    page = get_page()
    return _run_async(_async_browser_upload(page, element_uuid, file_paths))


def browser_download(element_uuid: str, save_dir: str = ".") -> str:
    """点击指定 UUID 对应的下载链接/按钮。"""
    page = get_page()
    return _run_async(_async_browser_download(page, element_uuid, save_dir))


def browser_switch(index: int) -> str:
    """切换到指定编号的标签页。"""
    return _run_async(_async_browser_switch(index))


# ── 工具分发处理器 ─────────────────────────────────────────────────────────

def dispatch(name: str, args: dict, ctx: ToolContext,
             work_model=None) -> ToolResult:
    """将 browse_* 工具名分发到对应处理函数。"""
    _handlers = {
        'browse_open':               _open,
        'browse_search':             _search,
        'browse_read':               _read,
        'browse_click':              _click,
        'browse_fill':               _fill,
        'browse_press':              _press,
        'browse_find':               _find,
        'browse_pdf':                _pdf,
        'browse_eval':               _eval,
        'browse_wait_for_navigation': _wait_for_navigation,
        'browse_hover':              _hover,
        'browse_select':             _select,
        'browse_get_url':            _get_url,
        'browse_scroll':             _scroll,
        'browse_upload':             _upload,
        'browse_download':           _download,
        'browse_switch':             _switch,
        'browse_close':              _close,
    }
    handler = _handlers.get(name)
    if handler is None:
        return ToolResult(text=f'Unknown browser tool: {name}')

    if name == 'browse_read':
        return handler(args, ctx, work_model=work_model)
    return handler(args, ctx)


# ── 各操作处理函数 ────────────────────────────────────────────────────────

def _open(args: dict, ctx: ToolContext) -> ToolResult:
    url = args.get('url', '')
    return ToolResult(
        text=browser_open(url),
        log_msg=f'Open Page: {url}',
        log_role='BROWSER',
    )


def _search(args: dict, ctx: ToolContext) -> ToolResult:
    query = args.get('query', '')
    engine = args.get('engine', 'google')
    return ToolResult(
        text=browser_search(query, engine),
        log_msg=f'Search ({engine}): {query}',
        log_role='BROWSER',
    )


def _read(args: dict, ctx: ToolContext, work_model=None) -> ToolResult:
    char_start = int(args.get('char_start', 0))
    char_end = int(args.get('char_end', 4000))
    mode = args.get('mode', 'all')

    result = browser_read(char_start, char_end, mode)

    # 历史去重
    try:
        current_url = get_page().url if get_page() and not get_page().is_closed() else None
    except Exception:
        current_url = None

    if current_url:
        prev = _browse_read_cache.get(current_url)
        if prev is not None and prev == result:
            result = f'<Page content unchanged. URL: {current_url}>'
            log(f'browse_read | Content unchanged: {current_url}')
        else:
            _browse_read_cache[current_url] = result

    return ToolResult(
        text=result,
        log_msg=f'Reading Page ({mode})',
        log_role='BROWSER',
    )


def _click(args: dict, ctx: ToolContext) -> ToolResult:
    uuid = args.get('element_uuid', '')
    return ToolResult(
        text=browser_click(uuid),
        log_msg=f'Click: [{uuid}]',
        log_role='BROWSER',
    )


def _fill(args: dict, ctx: ToolContext) -> ToolResult:
    uuid = args.get('element_uuid', '')
    text = args.get('text', '')
    return ToolResult(
        text=browser_fill(uuid, text),
        log_msg=f'Fill: [{uuid}] → {text!r}',
        log_role='BROWSER',
    )


def _press(args: dict, ctx: ToolContext) -> ToolResult:
    uuid = args.get('element_uuid', '')
    key = args.get('key', 'Enter')
    return ToolResult(
        text=browser_press(uuid, key),
        log_msg=f'Press: [{uuid}] {key!r}',
        log_role='BROWSER',
    )


def _find(args: dict, ctx: ToolContext) -> ToolResult:
    text = args.get('text', '')
    max_results = int(args.get('max_results', 10))
    return ToolResult(
        text=browser_find(text, max_results),
        log_msg=f'Page Search: {text!r}',
        log_role='BROWSER',
    )


def _pdf(args: dict, ctx: ToolContext) -> ToolResult:
    save_dir = args.get('save_dir') or ctx.cfg['work_dir']
    result = browser_pdf(save_dir)
    return ToolResult(
        text=result,
        log_msg=f'Save PDF → {save_dir}',
        log_role='BROWSER',
    )


def _eval(args: dict, ctx: ToolContext) -> ToolResult:
    script = args.get('script', '')
    return ToolResult(
        text=browser_eval(script),
        log_msg=f'Eval: \n{script}',
        log_role='BROWSER',
    )


def _wait_for_navigation(args: dict, ctx: ToolContext) -> ToolResult:
    timeout = args.get('timeout')
    state = args.get('state', 'networkidle')
    return ToolResult(
        text=browser_wait_for_navigation(timeout, state),
        log_msg=f'Loading ({state})...',
        log_role='BROWSER',
    )


def _hover(args: dict, ctx: ToolContext) -> ToolResult:
    uuid = args.get('element_uuid', '')
    return ToolResult(
        text=browser_hover(uuid),
        log_msg=f'Hover: [{uuid}]',
        log_role='BROWSER',
    )


def _select(args: dict, ctx: ToolContext) -> ToolResult:
    uuid = args.get('element_uuid', '')
    value = args.get('value', '')
    return ToolResult(
        text=browser_select(uuid, value),
        log_msg=f'Choose: [{uuid}] → {value!r}',
        log_role='BROWSER',
    )


def _get_url(args: dict, ctx: ToolContext) -> ToolResult:
    return ToolResult(
        text=browser_get_url(),
        log_msg='Get current URL',
        log_role='BROWSER',
    )


def _scroll(args: dict, ctx: ToolContext) -> ToolResult:
    direction = args.get('direction', 'down')
    amount = int(args.get('amount', 500))
    uuid = args.get('element_uuid') or None
    log_suffix = f'  [{uuid}]' if uuid else ''
    return ToolResult(
        text=browser_scroll(direction, amount, uuid),
        log_msg=f'Roll ({direction} {amount}px){log_suffix}',
        log_role='BROWSER',
    )


def _upload(args: dict, ctx: ToolContext) -> ToolResult:
    uuid = args.get('element_uuid', '')
    file_paths = args.get('file_paths', [])
    if isinstance(file_paths, str):
        file_paths = [file_paths]
    return ToolResult(
        text=browser_upload(uuid, file_paths),
        log_msg=f'Upload File: [{uuid}] ← {file_paths}',
        log_role='BROWSER',
    )


def _download(args: dict, ctx: ToolContext) -> ToolResult:
    uuid = args.get('element_uuid', '')
    save_dir = args.get('save_dir') or ctx.cfg.get('work_dir', '.')
    result = browser_download(uuid, save_dir)
    return ToolResult(
        text=result,
        log_msg=f'Download File: [{uuid}] → {save_dir}',
        log_role='BROWSER',
    )


def _switch(args: dict, ctx: ToolContext) -> ToolResult:
    index = int(args.get('index', 0))
    return ToolResult(
        text=browser_switch(index),
        log_msg=f'Switch Tab: [{index}]',
        log_role='BROWSER',
    )


def _close(args: dict, ctx: ToolContext) -> ToolResult:
    return ToolResult(
        text=browser_close(),
        log_msg='Close Browser',
        log_role='BROWSER',
    )
