"""
server/servers/browser/handler.py —— 浏览器工具处理器。

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

import hashlib
import os
import time
from typing import Optional
from urllib.parse import quote_plus

from logger import log
from server import ToolResult, ToolContext

# ── 导入 Playwright ────────────────────────────────────────────────────────
from rebrowser_playwright.sync_api import sync_playwright, Page, Browser, Playwright

# ── 全局单例 ──────────────────────────────────────────────────────────────
_pw: Optional["Playwright"] = None
_browser: Optional["Browser"] = None
_page: Optional["Page"] = None

# UUID → 元素元数据映射（每次 browse_read 后重建）
_item_map: dict[str, dict] = {}


# ── 可交互 role 列表（顺序决定枚举优先级）───────────────────────────────────
_INTERACTIVE_ROLES: list[str] = [
    'button', 'link', 'textbox', 'searchbox', 'combobox',
    'checkbox', 'radio', 'menuitem', 'menuitemcheckbox', 'menuitemradio',
    'option', 'switch', 'tab', 'slider', 'spinbutton',
    'listbox', 'treeitem', 'gridcell',
]
_INTERACTIVE_ROLES_SET = set(_INTERACTIVE_ROLES)


SEARCH_ENGINES = {
    'google': 'https://www.google.com/search?q=',
    'bing': 'https://www.bing.com/search?q=',
    'baidu': 'https://www.baidu.com/s?wd=',
    'duckduckgo': 'https://duckduckgo.com/?q=',
}


def _timeout_ms() -> int:
    try:
        from config import get_config
        return get_config().get('wait', 10) * 1000
    except Exception:
        return 10_000


def _make_uid(role: str, locator_name: str, index: int, seen: set) -> str:
    """基于 role + locator_name + index.md 生成稳定的 6 位 16 进制 ID，碰撞时加后缀。"""
    raw = hashlib.md5(f"{role}|{locator_name}|{index}".encode()).hexdigest()[:6]
    uid = raw
    while uid in seen:
        uid += "x"
    seen.add(uid)
    return uid


_CONTEXT_ERR = "Cannot find context with specified id"


def _safe_evaluate(page: "Page", script, arg=None, *, retries: int = 4,
                   base_delay: float = 0.4) -> object:
    """带重试的 page.evaluate()，专门应对 rebrowser-playwright context 竞态。

    rebrowser 每次导航后会重新注入反检测脚本，旧 context 会短暂失效，
    直接调用 evaluate() 会抛出 "Cannot find context with specified id"。
    本函数以指数退避重试，彻底消除该竞态窗口。

    Args:
        page:       Playwright Page 对象。
        script:     传给 page.evaluate() 的 JS 字符串或函数。
        arg:        可选参数，透传给 evaluate()。
        retries:    最大重试次数（默认 4）。
        base_delay: 首次重试等待秒数，后续翻倍（默认 0.4s）。
    Returns:
        evaluate() 的返回值。
    Raises:
        最后一次异常（非 context 错误会立即抛出）。
    """
    delay = base_delay
    last_exc: Exception | None = None
    for attempt in range(retries + 1):
        try:
            if arg is not None:
                return page.evaluate(script, arg)
            return page.evaluate(script)
        except Exception as e:
            err_str = str(e)
            if _CONTEXT_ERR not in err_str:
                raise  # 非 context 错误，立即抛出
            last_exc = e
            if attempt < retries:
                log(f"browser | _safe_evaluate context error (attempt {attempt + 1}/{retries}), "
                    f"retry in {delay:.1f}s...")
                time.sleep(delay)
                delay = min(delay * 2, 3.0)  # 指数退避，上限 3 秒
    raise last_exc


_USER_AGENT = (
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
    'AppleWebKit/537.36 (KHTML, like Gecko) '
    'Chrome/123.0.0.0 Safari/537.36'
)

_LAUNCH_ARGS = [
    '--disable-blink-features=AutomationControlled',
    '--no-sandbox',
    '--disable-dev-shm-usage',
]


def _ensure_browser(headless: bool = True) -> "Page":
    global _pw, _browser, _page

    if _page is None or _page.is_closed():
        if _browser is None or not _browser.is_connected():
            if _pw is None:
                _pw = sync_playwright().start()
            _browser = _pw.chromium.launch(headless=headless, args=_LAUNCH_ARGS)
        _page = _browser.new_page(user_agent=_USER_AGENT)
        log("browser | New browser page created [rebrowser-playwright]")

    return _page


# ── 无障碍树解析（基于 locator，兼容新版 Playwright）────────────────────

def _parse_ax_tree(page: "Page") -> tuple[list[str], list[dict]]:
    """用 locator 查询页面，返回 (text_lines, interactive_items)。

    text_lines:        页面正文文字行列表（过滤空行）
    interactive_items: list of {uuid, role, name, locator_index}
        - uuid:           8 位唯一 ID
        - role:           小写 role 字符串
        - name:           可访问名称（已保证非空）
        - locator_index:  该 role+name 组合下的第几个元素（0-based，用于精确定位）
    """
    text_lines: list[str] = []
    interactive_items: list[dict] = []

    # ── 正文：通过 JS 遍历可见文字节点 ─────────────────────────────────
    _js_text = """() => {
            const lines = [];
            const walker = document.createTreeWalker(
                document.body, NodeFilter.SHOW_TEXT, null
            );
            let node;
            while ((node = walker.nextNode())) {
                const t = node.textContent.trim();
                if (!t) continue;
                const el = node.parentElement;
                if (!el) continue;
                const tag = el.tagName;
                if (['SCRIPT','STYLE','NOSCRIPT'].includes(tag)) continue;
                if (el.offsetParent === null && tag !== 'BODY') continue;
                lines.push(t);
            }
            return lines;
        }"""
    try:
        raw_text = _safe_evaluate(page, _js_text)
        text_lines = [t for t in (raw_text or []) if t.strip()]
    except Exception as e:
        log(f"browser | text extraction error: {e}")

    # ── 可交互元素：按 role 逐一查询，不去重，全部保留 ────────────────────
    seen_uids: set = set()
    for role in _INTERACTIVE_ROLES:
        try:
            locator = page.get_by_role(role)  # type: ignore[arg-type]
            count = locator.count()
            if count == 0:
                continue
            for i in range(count):
                el = locator.nth(i)
                try:
                    _input_roles = {'textbox', 'searchbox', 'combobox', 'spinbutton'}
                    if role in _input_roles:
                        locator_name = (el.get_attribute('placeholder') or '').strip()
                        if not locator_name:
                            locator_name = (el.get_attribute('aria-label') or '').strip()
                        if not locator_name:
                            locator_name = (el.get_attribute('title') or '').strip()
                        current_val = (el.input_value(timeout=500) or '').strip()
                        name = f'[Fill: {current_val}]' if current_val else locator_name
                    else:
                        locator_name = (el.inner_text(timeout=500) or '').strip()
                        if not locator_name:
                            locator_name = (el.get_attribute('aria-label') or '').strip()
                        if not locator_name:
                            locator_name = (el.get_attribute('placeholder') or '').strip()
                        if not locator_name:
                            locator_name = (el.get_attribute('title') or '').strip()
                        if not locator_name:
                            locator_name = (el.get_attribute('value') or '').strip()
                        name = locator_name
                except Exception:
                    name = ''
                    locator_name = ''

                if not locator_name:
                    continue  # 无任何标识，跳过

                if not name:
                    name = locator_name

                try:
                    visible = el.is_visible()
                except Exception:
                    visible = False

                uid = _make_uid(role, locator_name, i, seen_uids)
                interactive_items.append({
                    'uuid': uid,
                    'role': role,
                    'name': name,
                    'locator_name': locator_name,
                    'locator_index': i,
                    'visible': visible,
                })
        except Exception as e:
            log(f"browser | role={role} query error: {e}")

    return text_lines, interactive_items


def _resolve_element(page: "Page", item: dict) -> Optional[object]:
    """根据 role + locator_name 精确定位 ElementHandle，优先取可见元素。

    定位策略（按优先级）：
      1. get_by_role(role, name=name, exact=True)   — 通用首选
      2. [仅 input 类] get_by_placeholder(name)     — textbox 常用 placeholder 作为标识
      3. [仅 input 类] get_by_label(name)           — 关联 <label> 文字
      4. [仅 input 类] CSS [id=...] / [name=...]    — 直接属性匹配
      5. get_by_text(name, exact=True)              — 兜底文字匹配
    """
    role = item['role']
    name = item['locator_name'] if item.get('locator_name') else item['name']
    idx = item.get('locator_index', 0)
    _input_roles = {'textbox', 'searchbox', 'combobox', 'spinbutton'}

    def _first_visible(locator) -> Optional[object]:
        """从 locator 中取第一个可见 ElementHandle；全不可见则取 nth(idx)。"""
        try:
            count = locator.count()
        except Exception:
            return None
        if count == 0:
            return None
        for i in range(count):
            try:
                handle = locator.nth(i).element_handle(timeout=1000)
                if handle and handle.is_visible():
                    if i != idx:
                        log(f"browser | _resolve_element skipped invisible nth({idx}), using nth({i})")
                    return handle
            except Exception:
                continue
        try:
            return locator.nth(idx).element_handle(timeout=3000)
        except Exception as e:
            log(f"browser | _resolve_element nth({idx}) fallback error: {e}")
        return None

    # ── 策略 1：get_by_role ───────────────────────────────────────────────
    try:
        h = _first_visible(page.get_by_role(role, name=name, exact=True))  # type: ignore[arg-type]
        if h:
            return h
    except Exception as e:
        log(f"browser | _resolve_element get_by_role error role={role} name={name!r}: {e}")

    # ── 策略 2 & 3 & 4：仅 input 类元素 ───────────────────────────────────
    if role in _input_roles:
        # 2. placeholder 精确匹配
        try:
            h = _first_visible(page.get_by_placeholder(name, exact=True))
            if h:
                log(f"browser | _resolve_element hit placeholder {name!r}")
                return h
        except Exception:
            pass

        # 3. 关联 label 文字
        try:
            h = _first_visible(page.get_by_label(name, exact=True))
            if h:
                log(f"browser | _resolve_element hit label {name!r}")
                return h
        except Exception:
            pass

        # 4. CSS 属性：[placeholder=...] / [aria-label=...] / [name=...]
        for attr in ('placeholder', 'aria-label', 'name'):
            try:
                sel = f'[{attr}="{name}"]'
                locator = page.locator(sel)
                h = _first_visible(locator)
                if h:
                    log(f"browser | _resolve_element hit css {sel}")
                    return h
            except Exception:
                continue

    # ── 策略 5：按可见文字兜底 ────────────────────────────────────────────
    try:
        h = _first_visible(page.get_by_text(name, exact=True))
        if h:
            return h
    except Exception as e:
        log(f"browser | _resolve_element get_by_text error name={name!r}: {e}")

    return None


# ── 辅助：新标签页检测 ───────────────────────────────────────────────────

def _maybe_switch_to_new_tab():
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


# ── 辅助：标签页列表 ─────────────────────────────────────────────────────

def _get_tabs_info() -> str:
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
            title = page.title()  # 降级：直接调用（不经过 evaluate）
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
    global _page, _item_map
    if _page is None or _page.is_closed():
        return "<The browser has not been opened yet>"

    # 检测新标签页
    _maybe_switch_to_new_tab()

    if mode not in ("interactive", "text", "all"):
        mode = "all"

    text_lines, interactive_items = _parse_ax_tree(_page)

    # 重建 UUID 映射
    _item_map = {item['uuid']: item for item in interactive_items}

    header = f"<Current: {_page.url}>\n<Read mode: {mode}>\n"
    tabs_info = _get_tabs_info()
    if tabs_info:
        header += tabs_info + "\n"

    sections: list[str] = []

    # 正文部分
    if mode in ("text", "all"):
        body = "\n".join(line for line in text_lines if line.strip())
        if len(body) > max_chars:
            body = (body[:max_chars] +
                    f"\n...(Truncated, totaling {len(body)} characters)"
                    f"<The max_chars parameter can be increased to read more>")
        if body:
            sections.append("<Text>\n" + body + "\n</Text>")

    # 可交互元素部分
    if mode in ("interactive", "all"):
        if interactive_items:
            lines = ["<Interactive Items>"]
            for item in interactive_items:
                vis = '' if item.get('visible', True) else '  (hidden)'
                lines.append(f"  [{item['uuid']}] {item['role']:<12}  {item['name']}{vis}")
            lines.append("</Interactive Items>")
            sections.append("\n".join(lines))
        elif mode == "interactive":
            sections.append("<Interactive Items>(NULL)</Interactive Items>")

    log(f"browser | READ mode={mode} text_lines={len(text_lines)} interactive={len(interactive_items)}")
    return header + "\n".join(sections)


def _refresh_item_map() -> str:
    """等待页面稳定后重建 UUID 映射，返回新增/消失的元素 diff。"""
    global _item_map
    _maybe_switch_to_new_tab()
    try:
        _page.wait_for_load_state("domcontentloaded", timeout=_timeout_ms())
    except Exception:
        pass
    try:
        _page.wait_for_load_state("networkidle", timeout=3000)
    except Exception:
        pass
    time.sleep(0.3)

    old_map = _item_map
    _, interactive_items = _parse_ax_tree(_page)
    new_map = {item['uuid']: item for item in interactive_items}
    _item_map = new_map
    log(f"browser | _refresh_item_map → {len(_item_map)} interactive elements")

    added = {uid: item for uid, item in new_map.items() if uid not in old_map}
    removed = {uid: item for uid, item in old_map.items() if uid not in new_map}

    parts = ["<The page has been refreshed. Consider using browser_read to get the latest information>"]
    if added:
        lines = [f"  [{uid}] {item['role']}  {item['name']}" for uid, item in added.items()]
        parts.append("<New Items>\n" + "\n".join(lines) + "\n</New Items>")
    if removed:
        lines = [f"  [{uid}] {item['role']}  {item['name']}" for uid, item in removed.items()]
        parts.append("<Missing Items>\n" + "\n".join(lines) + "\n</Missing Items>")
    if not added and not removed:
        parts.append("<Item list has not changed>")

    return "\n".join(parts)


def browser_click(element_uuid: str) -> str:
    """点击指定 UUID 对应的可交互元素。"""
    if _page is None or _page.is_closed():
        return "<The browser has not been opened yet>"

    item = _item_map.get(element_uuid)
    if item is None:
        known = ', '.join(_item_map.keys()) or '<The Mapping is empty, consider calling browse_read first>'
        return f"<Failed to Click: ID {element_uuid!r} does not exist. Available IDs: {known}>"

    label = f"[{element_uuid}] {item['role']} \"{item['name']}\""
    handle = _resolve_element(_page, item)
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
    if _page is None or _page.is_closed():
        return "<The browser has not been opened yet>"

    item = _item_map.get(element_uuid)
    if item is None:
        known = ', '.join(_item_map.keys()) or '<The Mapping is empty, consider calling browse_read first>'
        return f"<Failed to Fill: ID {element_uuid!r} does not exist. Available IDs: {known}>"

    role = item['role']
    label = f"[{element_uuid}] {role} \"{item['name']}\""

    _fillable = {'textbox', 'searchbox', 'combobox', 'spinbutton'}
    if role not in _fillable:
        return (f"<Failed to Fill: Element {label} type is {role!r}. Text fill not supported>"
                f"<Supported types: {', '.join(sorted(_fillable))}>")

    handle = _resolve_element(_page, item)
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
    if _page is None or _page.is_closed():
        return "<The browser has not been opened yet>"
    try:
        result = _safe_evaluate(_page, script)
        _page.wait_for_load_state("networkidle", timeout=_timeout_ms())
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
    if _page is None or _page.is_closed():
        return "<The browser has not been opened yet>"

    item = _item_map.get(element_uuid)
    if item is None:
        known = ', '.join(_item_map.keys()) or '(Mapping is empty, consider calling browse_read first)'
        return f"<Failed to Press: ID {element_uuid!r} does not exist. Available IDs: {known}>"

    label = f"[{element_uuid}] {item['role']} \"{item['name']}\""
    handle = _resolve_element(_page, item)
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
    if _page is None or _page.is_closed():
        return "<The browser has not been opened yet>"
    try:
        results = _safe_evaluate(
            _page,
            """([needle, limit]) => {
                const matches = [];
                const walker = document.createTreeWalker(
                    document.body, NodeFilter.SHOW_TEXT, null
                );
                let node;
                while ((node = walker.nextNode()) && matches.length < limit) {
                    if (!node.textContent.includes(needle)) continue;
                    const el = node.parentElement;
                    if (!el || el.offsetParent === null) continue;
                    let sel = el.tagName.toLowerCase();
                    if (el.id) sel += '#' + el.id;
                    else if (el.className && typeof el.className === 'string')
                        sel += '.' + el.className.trim().split(/\\s+/).join('.');
                    const snippet = node.textContent.trim().slice(0, 80);
                    matches.push({ tag: el.tagName.toLowerCase(), selector: sel, snippet });
                }
                return matches;
            }""",
            [text, max_results],
        )
        if not results:
            return f"<No visible elements containing {text!r} found on current page>"
        lines = [f"<Found {len(results)} elements containing {text!r} on the page:>"]
        for i, r in enumerate(results, 1):
            matched_uuid = next(
                (uid for uid, item in _item_map.items() if text in item['name']),
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
    if _page is None or _page.is_closed():
        return "<The browser has not been opened yet>"
    try:
        import base64
        os.makedirs(save_dir, exist_ok=True)
        filename = os.path.join(save_dir, f"page_{int(time.time())}.pdf")

        # 有头模式下 page.pdf() 不可用，改用 CDP Page.printToPDF
        cdp = _page.context.new_cdp_session(_page)
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
    if _page is None or _page.is_closed():
        return "<The browser has not been opened yet>"
    try:
        timeout_ms = (timeout if timeout is not None else (_timeout_ms() // 1000)) * 1000
        _page.wait_for_load_state(state, timeout=timeout_ms)
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
    global _page
    try:
        pages = _browser.contexts[0].pages if _browser and _browser.is_connected() else []
        if not pages:
            return "<No tabs currently open>"
        if index < 0 or index >= len(pages):
            return f"<Index {index} out of range, currently {len(pages)} tabs open (0 ~ {len(pages)-1})>"
        _page = pages[index]
        _page.bring_to_front()
        log(f"browser | SWITCH → [{index}] {_page.url}")
        return f"<Switched to tab [{index}]: {_page.title()}  {_page.url}>"
    except Exception as e:
        log(f"browser | SWITCH error: {e}")
        return f"<Failed to switch tab: {e}>"


def browser_hover(element_uuid: str) -> str:
    """将鼠标悬停在指定 UUID 对应的元素上，触发 hover 事件（如展开下拉菜单）。"""
    if _page is None or _page.is_closed():
        return "<The browser has not been opened yet>"

    item = _item_map.get(element_uuid)
    if item is None:
        known = ', '.join(_item_map.keys()) or '(Mapping is empty, consider calling browse_read first)'
        return f"<Failed to Hover: ID {element_uuid!r} does not exist. Available IDs: {known}>"

    label = f"[{element_uuid}] {item['role']} \"{item['name']}\""
    handle = _resolve_element(_page, item)
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

    value 可以是选项的 value 属性、label 文字，或 index.md（如 "0"、"1"）。
    """
    if _page is None or _page.is_closed():
        return "<The browser has not been opened yet>"

    item = _item_map.get(element_uuid)
    if item is None:
        known = ', '.join(_item_map.keys()) or '(Mapping is empty, consider calling browse_read first)'
        return f"<Failed to Select: ID {element_uuid!r} does not exist. Available IDs: {known}>"

    label = f"[{element_uuid}] {item['role']} \"{item['name']}\""
    handle = _resolve_element(_page, item)
    if handle is None:
        return f"<Failed to Select: Cannot locate element {label}>"

    try:
        # 尝试按 value、label、index.md 依次匹配
        select_args: dict = {}
        if value.isdigit():
            select_args['index.md'] = int(value)
        else:
            select_args['label'] = value  # Playwright 会自动 fallback 到 value

        selected = handle.select_option(**{k: v for k, v in select_args.items()},
                                        timeout=_timeout_ms())
        log(f"browser | SELECT {label} → {selected}")
        refresh_msg = _refresh_item_map()
        return f"<Selected in {label}: {selected}>\n{refresh_msg}"
    except Exception:
        # index.md 匹配失败时回退到按 value 精确匹配
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
    if _page is None or _page.is_closed():
        return "<The browser has not been opened yet>"
    try:
        url = _page.url
        title = _page.title() or "(No title)"
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
    if _page is None or _page.is_closed():
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
            item = _item_map.get(element_uuid)
            if item is None:
                return f"<Failed to Scroll: ID {element_uuid!r} does not exist, consider calling browse_read first>"
            handle = _resolve_element(_page, item)
            if handle is None:
                return f"<Failed to Scroll: Cannot locate element [{element_uuid}]>"
            handle.evaluate(
                f"el => el.scrollBy({delta_x}, {delta_y})"
            )
            label = f"element [{element_uuid}] \"{item['name']}\""
        else:
            _safe_evaluate(_page, f"window.scrollBy({delta_x}, {delta_y})")
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
    if _page is None or _page.is_closed():
        return "<The browser has not been opened yet>"

    if isinstance(file_paths, str):
        file_paths = [file_paths]

    # 验证文件存在
    missing = [p for p in file_paths if not os.path.isfile(p)]
    if missing:
        return f"<Upload failed: The following files does not exist:\n" + "\n".join(f"  {p}" for p in missing) + ">"

    item = _item_map.get(element_uuid)
    if item is None:
        known = ', '.join(_item_map.keys()) or '(Mapping is empty, consider calling browse_read first)'
        return f"<Failed to Upload: ID {element_uuid!r} does not exist. Available IDs: {known}>"

    label = f"[{element_uuid}] {item['role']} \"{item['name']}\""

    try:
        # Playwright 推荐用 expect_file_chooser 监听文件对话框
        with _page.expect_file_chooser(timeout=_timeout_ms()) as fc_info:
            handle = _resolve_element(_page, item)
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
            handle = _resolve_element(_page, item)
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
    if _page is None or _page.is_closed():
        return "<The browser has not been opened yet>"

    item = _item_map.get(element_uuid)
    if item is None:
        known = ', '.join(_item_map.keys()) or '(Mapping is empty, consider calling browse_read first)'
        return f"<Failed to Download: ID {element_uuid!r} does not exist. Available IDs: {known}>"

    label = f"[{element_uuid}] {item['role']} \"{item['name']}\""

    try:
        os.makedirs(save_dir, exist_ok=True)
        from config import get_config
        download_timeout_ms = get_config().get('wait_download', 60) * 1000
        with _page.expect_download(timeout=download_timeout_ms) as dl_info:
            handle = _resolve_element(_page, item)
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


def browser_close() -> str:
    """关闭浏览器及 Playwright 实例。"""
    global _pw, _browser, _page
    try:
        if _page and not _page.is_closed():
            _page.close()
        if _browser and _browser.is_connected():
            _browser.close()
        if _pw:
            _pw.stop()
        _page = _browser = _pw = None
        _item_map.clear()
        log("browser | Browser closed")
        return "<Browser closed>"
    except Exception as e:
        log(f"browser | CLOSE error: {e}")
        return f"<Error closing browser: {e}>"


def is_browser_open() -> bool:
    """检查浏览器是否已打开且可用。"""
    global _page, _browser
    if _page is None or _page.is_closed():
        return False
    if _browser is None or not _browser.is_connected():
        return False
    return True


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
        current_url = _page.url if _page and not _page.is_closed() else None
    except Exception:
        current_url = None
    file_key = f'browse_read:{current_url}' if current_url else None

    # 历史去重：与上一次内容对比，未变化则精简提示
    if work_model and file_key:
        prev = next(
            (m['file_contents'][file_key]
             for m in reversed(work_model._meta)
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
