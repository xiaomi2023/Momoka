"""
server/servers/browser/browser.py —— 浏览器工具处理器。

所有 browse_* 工具统一由 dispatch() 入口分发，
browse_read 的历史去重逻辑在此处处理（需要 work_model，由 router 传入）。

基于 Playwright 的浏览器操作模块（无障碍树版）。

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

import os
import time
from urllib.parse import quote_plus

from logger import log
from server.types import ToolResult, ToolContext
from server.servers.browser.util import (
    _load_js,
    _safe_evaluate,
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
)
from server.servers.browser.accessibility import (
    _parse_ax_tree,
    _resolve_element,
    _refresh_item_map,
)


# ── 核心操作函数 ─────────────────────────────────────────────────────────

def browser_open(url: str, wait_until: str = "domcontentloaded") -> str:
    """导航到指定 URL，返回页面标题。"""
    page = _ensure_browser()
    log(f"browser | OPEN {url}")
    try:
        page.goto(url, wait_until=wait_until, timeout=_timeout_ms())
        # 等待网络空闲，确保 rebrowser JS context 稳定后再返回
        try:
            page.wait_for_load_state("networkidle", timeout=5000)
        except Exception:
            pass  # 超时无妨，继续
        # rebrowser-playwright 每次导航后都会重新注入反检测脚本，
        # 此过程发生在 networkidle 之后，期间调用 evaluate() 会报
        # "Cannot find context with specified id"。
        # 用 _safe_evaluate 取标题，自带指数退避重试，比 sleep 更可靠。
        try:
            title = _safe_evaluate(page, "() => document.title")
        except Exception:
            title = page.title()  # 降级：直接调用 title() 同步属性
        return f"Open: {url}\nTitle: {title}"
    except Exception as e:
        log(f"browser | OPEN error: {e}")
        return f"<Failed to open Page: {e}>"


def browser_read(max_chars: int = 4000, mode: str = "all") -> str:
    """读取当前页面内容。

    mode:
        "interactive" — 只列出可交互元素（UUID、类型、标签文字）
        "text"        — 只显示页面正文
        "all"         — 正文 + 可交互元素（默认）
    """
    page = get_page()
    if page is None or page.is_closed():
        return "<The browser has not been opened yet>"

    # 检测新标签页
    _maybe_switch_to_new_tab()

    if mode not in ("interactive", "text", "all"):
        mode = "all"

    text_lines, interactive_items = _parse_ax_tree(page)

    # 重建 UUID 映射
    set_item_map({item['uuid']: item for item in interactive_items})

    header = f"<Current: {page.url}>\n<Read mode: {mode}>\n"
    tabs_info = _get_tabs_info()
    if tabs_info:
        header += tabs_info + "\n"

    sections: list[str] = []

    # 正文部分
    if mode in ("text", "all"):
        body = "\n".join(line for line in text_lines if line.strip())
        if len(body) > max_chars:
            body = (body[:max_chars] +
                    f"\n...(Truncated, totaling {len(body)} characters)\n"
                    f"<The max_chars parameter can be increased to read more>")
        if body:
            sections.append("<Text>\n" + body + "\n</Text>")

    # 可交互元素部分
    if mode in ("interactive", "all"):
        if interactive_items:
            lines = ["<Interactive Items>"]
            for item in interactive_items:
                vis = '' if item.get('visible', True) else '  (hidden)'

                # 构建额外属性显示
                extra_info = ''

                # 禁用状态（优先显示）
                if item.get('disabled'):
                    extra_info += '  [Disabled]'

                # 输入框：显示当前填充值、字段标签和输入类型
                if item.get('fill'):
                    extra_info += f'  [Fill: {item["fill"]}]'
                if item.get('field_label'):
                    extra_info += f'  [Label: {item["field_label"]}]'
                if item.get('input_type'):
                    extra_info += f' (type={item["input_type"]})'

                # 复选框/单选框：显示选中状态
                if 'checked' in item:
                    extra_info += f'  [Checked: {item["checked"]}]'

                # 按钮：显示状态
                if item.get('state'):
                    extra_info += f'  [State: {item["state"]}]'

                lines.append(f"  [{item['uuid']}] {item['role']:<12}  {item['name']}{vis}{extra_info}")
            lines.append("</Interactive Items>")
            sections.append("\n".join(lines))
        elif mode == "interactive":
            sections.append("<Interactive Items>(NULL)</Interactive Items>")

    log(f"browser | READ mode={mode} text_lines={len(text_lines)} interactive={len(interactive_items)}")
    return header + "\n".join(sections)


def browser_click(element_uuid: str) -> str:
    """点击指定 UUID 对应的可交互元素。"""
    page = get_page()
    if page is None or page.is_closed():
        return "<The browser has not been opened yet>"

    item = get_item_map().get(element_uuid)
    if item is None:
        known = ', '.join(get_item_map().keys()) or '<The Mapping is empty, consider calling browse_read first>'
        return f"<Failed to Click: ID {element_uuid!r} does not exist. Available IDs: {known}>"

    label = f"[{element_uuid}] {item['role']} \"{item['name']}\""
    handle = _resolve_element(page, item)
    if handle is None:
        return f"<Failed to Click: Cannot locate element {label}>"

    try:
        handle.click(timeout=_timeout_ms())
        log(f"browser | CLICK {label}")
        refresh_msg = _refresh_item_map()
        return f"<Clicked: {label}\n{refresh_msg}>"
    except Exception as e:
        log(f"browser | CLICK error {label}: {e}")
        return f"<Failed to Click {label}: {e}>"


def browser_fill(element_uuid: str, text: str) -> str:
    """向指定 UUID 对应的 textbox / searchbox / combobox 填充文字。"""
    page = get_page()
    if page is None or page.is_closed():
        return "<The browser has not been opened yet>"

    item = get_item_map().get(element_uuid)
    if item is None:
        known = ', '.join(get_item_map().keys()) or '<The Mapping is empty, consider calling browse_read first>'
        return f"<Failed to Fill: ID {element_uuid!r} does not exist. Available IDs: {known}>"

    role = item['role']
    label = f"[{element_uuid}] {role} \"{item['name']}\""

    _fillable = {'textbox', 'searchbox', 'combobox', 'spinbutton'}
    if role not in _fillable:
        return (f"<Failed to Fill: Element {label} type is {role!r}. Text fill not supported>"
                f"<Supported types: {', '.join(sorted(_fillable))}>")

    handle = _resolve_element(page, item)
    if handle is None:
        return f"<Failed to Fill: Cannot locate element {label}>"

    try:
        handle.fill(text, timeout=_timeout_ms())
        log(f"browser | FILL {label} → {text!r}")
        refresh_msg = _refresh_item_map()
        return f"<Filled element {label} with: {text!r}>\n{refresh_msg}"
    except Exception as e:
        log(f"browser | FILL error {label}: {e}")
        return f"<Failed to Fill {label}: {e}>"


def browser_eval(script: str) -> str:
    """在当前页面执行 JavaScript，返回结果字符串。"""
    page = get_page()
    if page is None or page.is_closed():
        return "<The browser has not been opened yet>"
    try:
        result = _safe_evaluate(page, script)
        page.wait_for_load_state("networkidle", timeout=_timeout_ms())
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


def browser_press(element_uuid: str, key: str) -> str:
    """向指定 UUID 元素发送真实按键（如 Enter、Tab、Escape 等）。

    使用 Playwright 原生 press()，可正确触发页面的键盘事件监听器。
    按键后自动刷新 UUID 映射。
    常用 key 值: Enter, Tab, Escape, ArrowDown, ArrowUp, Backspace
    """
    page = get_page()
    if page is None or page.is_closed():
        return "<The browser has not been opened yet>"

    item = get_item_map().get(element_uuid)
    if item is None:
        known = ', '.join(get_item_map().keys()) or '(Mapping is empty, consider calling browse_read first)'
        return f"<Failed to Press: ID {element_uuid!r} does not exist. Available IDs: {known}>"

    label = f"[{element_uuid}] {item['role']} \"{item['name']}\""
    handle = _resolve_element(page, item)
    if handle is None:
        return f"<Failed to Press: Cannot locate element {label}>"

    try:
        handle.press(key, timeout=_timeout_ms())
        log(f"browser | PRESS {label} key={key!r}")
        refresh_msg = _refresh_item_map()
        return f"<Pressed key {key!r} on element {label}>\n{refresh_msg}"
    except Exception as e:
        log(f"browser | PRESS error {label}: {e}")
        return f"<Failed to Press {label}: {e}>"


def browser_find(text: str, max_results: int = 10) -> str:
    """在当前页面中搜索包含指定文字的可见元素。"""
    page = get_page()
    if page is None or page.is_closed():
        return "<The browser has not been opened yet>"
    try:
        results = _safe_evaluate(
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


def browser_pdf(save_dir: str = ".") -> str:
    """将当前页面打印为 PDF。

    headless 模式：直接调用 page.pdf()。
    有头模式（rebrowser）：通过 CDP Page.printToPDF 命令实现，效果等同。
    """
    page = get_page()
    if page is None or page.is_closed():
        return "<The browser has not been opened yet>"
    try:
        import base64
        os.makedirs(save_dir, exist_ok=True)
        filename = os.path.join(save_dir, f"page_{int(time.time())}.pdf")

        # 有头模式下 page.pdf() 不可用，改用 CDP Page.printToPDF
        cdp = page.context.new_cdp_session(page)
        result = cdp.send("Page.printToPDF", {
            "printBackground": True,
            "paperWidth": 8.27,   # A4 英寸
            "paperHeight": 11.69,
        })
        cdp.detach()
        pdf_bytes = base64.b64decode(result["data"])
        with open(filename, "wb") as f:
            f.write(pdf_bytes)
        size = os.path.getsize(filename)
        log(f"browser | PDF saved to {filename} ({size} bytes)")
        return f"PDF has been saved at: {filename} ({size / 1024:.1f} KB)"
    except Exception as e:
        log(f"browser | PDF error: {e}")
        return f"Failed at generating PDF: {e}"


def browser_wait_for_navigation(timeout: int = None, state: str = "networkidle") -> str:
    """等待页面导航完成。"""
    page = get_page()
    if page is None or page.is_closed():
        return "<The browser has not been opened yet>"
    try:
        timeout_ms = (timeout if timeout is not None else (_timeout_ms() // 1000)) * 1000
        page.wait_for_load_state(state, timeout=timeout_ms)
        log(f"browser | WAIT completed: state={state}")
        return f"<Page load completed (state: {state})>"
    except Exception as e:
        log(f"browser | WAIT error: {e}")
        return f"<Failed to wait for page load: {e}>"


def browser_search(query: str, engine: str = 'google') -> str:
    """使用指定搜索引擎搜索关键词。"""
    engine = engine.lower()
    base_url = SEARCH_ENGINES.get(engine)
    if base_url is None:
        return f"<Unsupported search engine: {engine!r}. Supported: {', '.join(SEARCH_ENGINES)}>"
    url = base_url + quote_plus(query)
    log(f"browser | SEARCH [{engine}] {query!r} → {url}")
    page = _ensure_browser()
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=_timeout_ms())
        # 搜索结果页可能有重定向，额外等待网络空闲，确保 JS context 稳定
        try:
            page.wait_for_load_state("networkidle", timeout=5000)
        except Exception:
            pass  # 超时无妨，继续
        # 用 _safe_evaluate 取标题，带指数退避重试，比 sleep 更可靠
        try:
            title = _safe_evaluate(page, "() => document.title")
        except Exception:
            title = page.title()
        return f"<Opened page: {url}\nTitle: {title}>"
    except Exception as e:
        log(f"browser | SEARCH error: {e}")
        return f"<Search failed: {e}>"


def browser_switch(index: int) -> str:
    """切换到指定编号的标签页。"""
    from server.servers.browser.browser_state import get_browser, set_page
    browser = get_browser()
    page = get_page()
    try:
        pages = browser.contexts[0].pages if browser and browser.is_connected() else []
        if not pages:
            return "<No tabs currently open>"
        if index < 0 or index >= len(pages):
            return f"<Index {index} out of range, currently {len(pages)} tabs open (0 ~ {len(pages)-1})>"
        set_page(pages[index])
        pages[index].bring_to_front()
        log(f"browser | SWITCH → [{index}] {pages[index].url}")
        return f"<Switched to tab [{index}]: {pages[index].title()}  {pages[index].url}>"
    except Exception as e:
        log(f"browser | SWITCH error: {e}")
        return f"<Failed to switch tab: {e}>"


def browser_hover(element_uuid: str) -> str:
    """将鼠标悬停在指定 UUID 对应的元素上，触发 hover 事件（如展开下拉菜单）。"""
    page = get_page()
    if page is None or page.is_closed():
        return "<The browser has not been opened yet>"

    item = get_item_map().get(element_uuid)
    if item is None:
        known = ', '.join(get_item_map().keys()) or '(Mapping is empty, consider calling browse_read first)'
        return f"<Failed to Hover: ID {element_uuid!r} does not exist. Available IDs: {known}>"

    label = f"[{element_uuid}] {item['role']} \"{item['name']}\""
    handle = _resolve_element(page, item)
    if handle is None:
        return f"<Failed to Hover: Cannot locate element {label}>"

    try:
        handle.hover(timeout=_timeout_ms())
        log(f"browser | HOVER {label}")
        refresh_msg = _refresh_item_map()
        return f"<Hovered over element: {label}>\n{refresh_msg}"
    except Exception as e:
        log(f"browser | HOVER error {label}: {e}")
        return f"<Failed to Hover {label}: {e}>"


def browser_select(element_uuid: str, value: str) -> str:
    """在指定 UUID 对应的 <select> 下拉框中选择选项。

    value 可以是选项的 value 属性、label 文字，或 index（如 "0"、"1"）。
    """
    page = get_page()
    if page is None or page.is_closed():
        return "<The browser has not been opened yet>"

    item = get_item_map().get(element_uuid)
    if item is None:
        known = ', '.join(get_item_map().keys()) or '(Mapping is empty, consider calling browse_read first)'
        return f"<Failed to Select: ID {element_uuid!r} does not exist. Available IDs: {known}>"

    label = f"[{element_uuid}] {item['role']} \"{item['name']}\""
    handle = _resolve_element(page, item)
    if handle is None:
        return f"<Failed to Select: Cannot locate element {label}>"

    try:
        # 尝试按 value、label、index 依次匹配
        select_args: dict = {}
        if value.isdigit():
            select_args['index'] = int(value)
        else:
            select_args['label'] = value  # Playwright 会自动 fallback 到 value

        selected = handle.select_option(**{k: v for k, v in select_args.items()},
                                        timeout=_timeout_ms())
        log(f"browser | SELECT {label} → {selected}")
        refresh_msg = _refresh_item_map()
        return f"<Selected in {label}: {selected}>\n{refresh_msg}"
    except Exception:
        # index 匹配失败时回退到按 value 精确匹配
        try:
            selected = handle.select_option(value=value, timeout=_timeout_ms())
            log(f"browser | SELECT (value fallback) {label} → {selected}")
            refresh_msg = _refresh_item_map()
            return f"<Selected in {label}: {selected}>\n{refresh_msg}"
        except Exception as e:
            log(f"browser | SELECT error {label}: {e}")
        return f"<Failed to Select {label}: {e}>"


def browser_get_url() -> str:
    """返回当前页面的 URL 和标题，用于快速确认页面状态而无需完整读取内容。"""
    page = get_page()
    if page is None or page.is_closed():
        return "<The browser has not been opened yet>"
    try:
        url = page.url
        title = page.title() or "(No title)"
        log(f"browser | GET_URL {url}")
        return f"<Current Page>\n  URL:   {url}\n  Title: {title}"
    except Exception as e:
        log(f"browser | GET_URL error: {e}")
        return f"<Failed to get URL: {e}>"


def browser_scroll(direction: str = "down", amount: int = 500,
                   element_uuid: str | None = None) -> str:
    """滚动页面或指定元素。

    Args:
        direction:    滚动方向，'up' / 'down' / 'left' / 'right'，默认 'down'。
        amount:       滚动像素数，默认 500。
        element_uuid: 可选。若传入则滚动该元素内部，否则滚动整个页面。
    """
    page = get_page()
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
            handle = _resolve_element(page, item)
            if handle is None:
                return f"<Failed to Scroll: Cannot locate element [{element_uuid}]>"
            handle.evaluate(
                f"el => el.scrollBy({delta_x}, {delta_y})"
            )
            label = f"element [{element_uuid}] \"{item['name']}\""
        else:
            _safe_evaluate(page, f"window.scrollBy({delta_x}, {delta_y})")
            label = "page"

        log(f"browser | SCROLL {label} {direction} {amount}px")
        refresh_msg = _refresh_item_map()
        return f"<Scrolled {label} {direction} by {amount}px>\n{refresh_msg}"
    except Exception as e:
        log(f"browser | SCROLL error: {e}")
        return f"<Failed to Scroll: {e}>"


def browser_upload(element_uuid: str, file_paths: list[str] | str) -> str:
    """向指定 UUID 对应的文件选择框（<input type="file">）上传一个或多个本地文件。

    Args:
        element_uuid: browse_read 返回的元素 UUID（role 通常为 button 或直接暴露为 input）。
        file_paths:   本地文件路径，字符串（单文件）或列表（多文件）。
                      路径必须是绝对路径或相对于当前工作目录的路径。
    """
    page = get_page()
    if page is None or page.is_closed():
        return "<The browser has not been opened yet>"

    if isinstance(file_paths, str):
        file_paths = [file_paths]

    # 验证文件存在
    missing = [p for p in file_paths if not os.path.isfile(p)]
    if missing:
        return f"<Upload failed: The following files does not exist:\n" + "\n".join(f"  {p}" for p in missing) + ">"

    item = get_item_map().get(element_uuid)
    if item is None:
        known = ', '.join(get_item_map().keys()) or '(Mapping is empty, consider calling browse_read first)'
        return f"<Failed to Upload: ID {element_uuid!r} does not exist. Available IDs: {known}>"

    label = f"[{element_uuid}] {item['role']} \"{item['name']}\""

    try:
        # Playwright 推荐用 expect_file_chooser 监听文件对话框
        with page.expect_file_chooser(timeout=_timeout_ms()) as fc_info:
            handle = _resolve_element(page, item)
            if handle is None:
                return f"<Failed to Upload: Cannot locate element {label}>"
            handle.click(timeout=_timeout_ms())
        fc_info.value.set_files(file_paths)
        names = ", ".join(os.path.basename(p) for p in file_paths)
        log(f"browser | UPLOAD {label} ← {file_paths}")
        refresh_msg = _refresh_item_map()
        return f"<Uploaded {len(file_paths)} file(s) to {label}: {names}>\n{refresh_msg}"
    except Exception as e:
        # 回退：直接对 input[type=file] 调用 set_input_files
        try:
            handle = _resolve_element(page, item)
            if handle is None:
                return f"<Failed to Upload: Cannot locate element {label}: {e}>"
            handle.set_input_files(file_paths, timeout=_timeout_ms())
            names = ", ".join(os.path.basename(p) for p in file_paths)
            log(f"browser | UPLOAD (set_input_files fallback) {label} ← {file_paths}")
            refresh_msg = _refresh_item_map()
            return f"<Uploaded {len(file_paths)} file(s) to {label}: {names}>\n{refresh_msg}"
        except Exception as e2:
            log(f"browser | UPLOAD error {label}: {e2}")
            return f"<Failed to Upload {label}: {e2}>"


def browser_download(element_uuid: str, save_dir: str = ".") -> str:
    """点击指定 UUID 对应的下载链接/按钮，等待下载完成并将文件保存到指定目录。

    Args:
        element_uuid: browse_read 返回的元素 UUID。
        save_dir:     文件保存目录，默认为当前工作目录。
    """
    page = get_page()
    if page is None or page.is_closed():
        return "<The browser has not been opened yet>"

    item = get_item_map().get(element_uuid)
    if item is None:
        known = ', '.join(get_item_map().keys()) or '(Mapping is empty, consider calling browse_read first)'
        return f"<Failed to Download: ID {element_uuid!r} does not exist. Available IDs: {known}>"

    label = f"[{element_uuid}] {item['role']} \"{item['name']}\""

    try:
        os.makedirs(save_dir, exist_ok=True)
        from config import get_config
        download_timeout_ms = get_config().get('wait_download', 60) * 1000
        with page.expect_download(timeout=download_timeout_ms) as dl_info:
            handle = _resolve_element(page, item)
            if handle is None:
                return f"<Failed to Download: Cannot locate element {label}>"
            handle.click(timeout=_timeout_ms())
        download = dl_info.value
        suggested = download.suggested_filename or f"download_{int(time.time())}"
        save_path = os.path.join(save_dir, suggested)
        download.save_as(save_path)
        size = os.path.getsize(save_path)
        log(f"browser | DOWNLOAD {label} → {save_path} ({size} bytes)")
        refresh_msg = _refresh_item_map()
        return f"<Download completed: {save_path} ({size / 1024:.1f} KB)>\n{refresh_msg}"
    except Exception as e:
        log(f"browser | DOWNLOAD error {label}: {e}")
        return f"<Failed to Download {label}: {e}>"


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
    max_chars = int(args.get('max_chars', 4000))
    mode = args.get('mode', 'all')

    result = browser_read(max_chars, mode)

    # 构造文件键
    try:
        current_url = get_page().url if get_page() and not get_page().is_closed() else None
    except Exception:
        current_url = None
    file_key = f'browse_read:{current_url}' if current_url else None

    # 历史去重：与上一次内容对比，未变化则精简提示
    if work_model and file_key:
        prev = next(
            (m['file_contents'][file_key]
             for m in reversed(work_model.meta)
             if file_key in m.get('file_contents', {})),
            None,
        )
        if prev is not None and prev == result:
            url = file_key.removeprefix('browse_read:')
            result = f'<Page content unchanged. URL: {url}>'
            log(f'browse_read | Content unchanged: {url}')

    file_contents = {file_key: result} if file_key else {}
    return ToolResult(
        text=result,
        file_contents=file_contents,
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


def _close(args: dict, ctx: ToolContext) -> ToolResult:
    return ToolResult(
        text=browser_close(),
        log_msg='Close Browser',
        log_role='BROWSER',
    )
