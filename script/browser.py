"""
browser.py —— 基于 Playwright 的浏览器操作模块（无障碍树版）。

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
from typing import Optional

from script.logger import log, user_log


def _timeout_ms() -> int:
    try:
        from config import get_config
        return get_config().get('wait', 10) * 1000
    except Exception:
        return 10_000


# ── 延迟导入 Playwright（优先使用 rebrowser_playwright）────────────────
try:
    from rebrowser_playwright.sync_api import sync_playwright, Page, Browser, Playwright
    _PLAYWRIGHT_AVAILABLE = True
    _USING_REBROWSER = True
except ImportError:
    _USING_REBROWSER = False
    try:
        from playwright.sync_api import sync_playwright, Page, Browser, Playwright
        _PLAYWRIGHT_AVAILABLE = True
    except ImportError:
        _PLAYWRIGHT_AVAILABLE = False

# ── 全局单例 ──────────────────────────────────────────────────────────────
_pw: Optional["Playwright"] = None
_browser: Optional["Browser"] = None
_page: Optional["Page"] = None

# UUID → 元素元数据映射（每次 browse_read 后重建）
_item_map: dict[str, dict] = {}

# 全局递增计数器，每次 browse_read 时从1重新计数
_uuid_counter: int = 0


def _next_uuid() -> str:
    global _uuid_counter
    _uuid_counter += 1
    return str(_uuid_counter)


def _ensure_browser(headless: bool = True) -> "Page":
    global _pw, _browser, _page

    if not _PLAYWRIGHT_AVAILABLE:
        raise RuntimeError(
            "Playwright is not installed. Please run: pip install rebrowser-playwright && "
            "python -m rebrowser_playwright install chromium"
        )

    if _page is None or _page.is_closed():
        if _browser is None or not _browser.is_connected():
            if _pw is None:
                if not _USING_REBROWSER:
                    user_log(
                        "rebrowser-playwright is not installed, falling back to playwright",
                        role='WARN',
                    )
                _pw = sync_playwright().start()
            _browser = _pw.chromium.launch(headless=headless)
        _page = _browser.new_page()
        backend = "rebrowser-playwright" if _USING_REBROWSER else "playwright"
        log(f"browser | 新建浏览器页面 [{backend}]")

    return _page


# ── 无障碍树解析（基于 locator，兼容新版 Playwright）────────────────────

# 可交互 role 列表（顺序决定枚举优先级）
_INTERACTIVE_ROLES: list[str] = [
    'button', 'link', 'textbox', 'searchbox', 'combobox',
    'checkbox', 'radio', 'menuitem', 'menuitemcheckbox', 'menuitemradio',
    'option', 'switch', 'tab', 'slider', 'spinbutton',
    'listbox', 'treeitem', 'gridcell',
]
_INTERACTIVE_ROLES_SET = set(_INTERACTIVE_ROLES)


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
    for _attempt in range(3):
        try:
            raw_text = page.evaluate(_js_text)
            text_lines = [t for t in (raw_text or []) if t.strip()]
            break
        except Exception as e:
            _err_str = str(e)
            # rebrowser-playwright context 切换竞态：稍等后重试
            if "Cannot find context with specified id" in _err_str and _attempt < 2:
                log(f"browser | text extraction context error (attempt {_attempt+1}), retrying...")
                time.sleep(0.5)  # 增大重试间隔，给上下文切换更多稳定时间
                continue
            log(f"browser | text extraction error: {e}")
            break

    # ── 可交互元素：按 role 逐一查询，不去重，全部保留 ────────────────────
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
                        name = f'[已填充: {current_val}]' if current_val else locator_name
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

                uid = _next_uuid()
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
                        log(f"browser | _resolve_element 跳过不可见 nth({idx})，改用 nth({i})")
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
                log(f"browser | 检测到新标签页，自动切换: {old_url} → {_page.url}")
    except Exception as e:
        log(f"browser | 新标签页检测失败: {e}")


# ── 辅助：标签页列表 ─────────────────────────────────────────────────────

def _get_tabs_info() -> str:
    try:
        pages = _browser.contexts[0].pages if _browser and _browser.is_connected() else []
        if not pages:
            return ""
        lines = []
        for i, p in enumerate(pages):
            marker = " ◀ 当前" if p == _page else ""
            try:
                title = p.title() or "(无标题)"
            except Exception:
                title = "(无法获取)"
            lines.append(f"  [{i}] {title}  {p.url}{marker}")
        return "<标签页列表>\n" + "\n".join(lines) + "\n</标签页列表>"
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
        # "Cannot find context with specified id"，需统一等待稳定。
        if _USING_REBROWSER:
            time.sleep(0.5)  # 给 rebrowser 注入脚本留出稳定窗口（对所有页面生效）
        title = page.title()
        return f"已打开页面: {url}\n标题: {title}"
    except Exception as e:
        log(f"browser | OPEN error: {e}")
        return f"打开页面失败: {e}"


def browser_read(max_chars: int = 4000, mode: str = "all") -> str:
    """读取当前页面内容。

    mode:
        "interactive" — 只列出可交互元素（UUID、类型、标签文字）
        "text"        — 只显示页面正文
        "all"         — 正文 + 可交互元素（默认）
    """
    global _page, _item_map
    if _page is None or _page.is_closed():
        return "浏览器尚未打开任何页面，请先使用 BROWSE_OPEN。"

    # 检测新标签页
    _maybe_switch_to_new_tab()

    if mode not in ("interactive", "text", "all"):
        mode = "all"

    global _uuid_counter
    _uuid_counter = 0
    text_lines, interactive_items = _parse_ax_tree(_page)

    # 重建 UUID 映射
    _item_map = {item['uuid']: item for item in interactive_items}

    header = f"<当前页面: {_page.url}>\n<读取模式: {mode}>\n"
    tabs_info = _get_tabs_info()
    if tabs_info:
        header += tabs_info + "\n"

    sections: list[str] = []

    # 正文部分
    if mode in ("text", "all"):
        body = "\n".join(line for line in text_lines if line.strip())
        if len(body) > max_chars:
            body = (body[:max_chars] +
                    f"\n…（正文已截断，共 {len(body)} 字符。可增大 max_chars 参数读取更多）")
        if body:
            sections.append("<正文>\n" + body + "\n</正文>")

    # 可交互元素部分
    if mode in ("interactive", "all"):
        if interactive_items:
            lines = ["<可交互元素>"]
            for item in interactive_items:
                vis = '' if item.get('visible', True) else '  (隐藏)'
                lines.append(f"  [{item['uuid']}] {item['role']:<12}  {item['name']}{vis}")
            lines.append("</可交互元素>")
            sections.append("\n".join(lines))
        elif mode == "interactive":
            sections.append("<可交互元素>（当前页面未检测到可交互元素）</可交互元素>")

    log(f"browser | READ mode={mode} text_lines={len(text_lines)} interactive={len(interactive_items)}")
    return header + "\n".join(sections)


def _refresh_item_map() -> str:
    """等待页面稳定后重建 UUID 映射，返回简短的状态描述。"""
    global _item_map, _uuid_counter
    _maybe_switch_to_new_tab()
    try:
        _page.wait_for_load_state("domcontentloaded", timeout=_timeout_ms())
    except Exception:
        pass
    try:
        _page.wait_for_load_state("networkidle", timeout=3000)
    except Exception:
        pass
    _uuid_counter = 0
    _, interactive_items = _parse_ax_tree(_page)
    _item_map = {item['uuid']: item for item in interactive_items}
    log(f"browser | _refresh_item_map → {len(_item_map)} 个可交互元素")
    return f"（页面已刷新）\n<警告：交互元素ID信息可能已经过期。使用 browser_read 获取最新的交互元素 ID 信息。>"


def browser_click(element_uuid: str) -> str:
    """点击指定 UUID 对应的可交互元素。"""
    if _page is None or _page.is_closed():
        return "浏览器尚未打开任何页面。"

    item = _item_map.get(element_uuid)
    if item is None:
        known = ', '.join(_item_map.keys()) or '（映射为空，请先调用 browse_read）'
        return f"点击失败: ID {element_uuid!r} 不存在。当前已知 ID: {known}"

    label = f"[{element_uuid}] {item['role']} \"{item['name']}\""
    handle = _resolve_element(_page, item)
    if handle is None:
        return f"点击失败: 无法定位元素 {label}"

    try:
        handle.click(timeout=_timeout_ms())
        log(f"browser | CLICK {label}")
        refresh_msg = _refresh_item_map()
        return f"已点击元素: {label}\n{refresh_msg}"
    except Exception as e:
        log(f"browser | CLICK error {label}: {e}")
        return f"点击失败 {label}: {e}"


def browser_fill(element_uuid: str, text: str) -> str:
    """向指定 UUID 对应的 textbox / searchbox / combobox 填充文字。"""
    if _page is None or _page.is_closed():
        return "浏览器尚未打开任何页面。"

    item = _item_map.get(element_uuid)
    if item is None:
        known = ', '.join(_item_map.keys()) or '（映射为空，请先调用 browse_read）'
        return f"填充失败: ID {element_uuid!r} 不存在。当前已知 ID: {known}"

    role = item['role']
    label = f"[{element_uuid}] {role} \"{item['name']}\""

    _fillable = {'textbox', 'searchbox', 'combobox', 'spinbutton'}
    if role not in _fillable:
        return (f"填充失败: 元素 {label} 类型为 {role!r}，不支持文字填充。"
                f"可填充类型: {', '.join(sorted(_fillable))}")

    handle = _resolve_element(_page, item)
    if handle is None:
        return f"填充失败: 无法定位元素 {label}"

    try:
        handle.fill(text, timeout=_timeout_ms())
        log(f"browser | FILL {label} → {text!r}")
        refresh_msg = _refresh_item_map()
        return f"已填充元素 {label}，内容: {text!r}\n{refresh_msg}"
    except Exception as e:
        log(f"browser | FILL error {label}: {e}")
        return f"填充失败 {label}: {e}"


def browser_eval(script: str) -> str:
    """在当前页面执行 JavaScript，返回结果字符串。"""
    if _page is None or _page.is_closed():
        return "浏览器尚未打开任何页面。"
    try:
        result = _page.evaluate(script)
        _page.wait_for_load_state("networkidle", timeout=_timeout_ms())
        log(f"browser | EVAL result: {result}")
        base_msg = f"JavaScript 执行结果: {result}"
        async_keywords = ['setTimeout', 'setInterval', 'Promise', 'async', 'await']
        if any(k in script for k in async_keywords):
            base_msg += "\n<警告: 检测到可能包含异步操作，结果可能不完整。>"
        return base_msg
    except Exception as e:
        log(f"browser | EVAL error: {e}")
        err_msg = f"JavaScript 执行失败: {e}"
        if "return" in script:
            err_msg += "\n<提示: 顶层不能有 return 语句。多步逻辑请用 IIFE: (() => { ...; return result; })()>"
        return err_msg


def browser_press(element_uuid: str, key: str) -> str:
    """向指定 UUID 元素发送真实按键（如 Enter、Tab、Escape 等）。

    使用 Playwright 原生 press()，可正确触发页面的键盘事件监听器。
    按键后自动刷新 UUID 映射。
    常用 key 值: Enter, Tab, Escape, ArrowDown, ArrowUp, Backspace
    """
    if _page is None or _page.is_closed():
        return "浏览器尚未打开任何页面。"

    item = _item_map.get(element_uuid)
    if item is None:
        known = ', '.join(_item_map.keys()) or '（映射为空，请先调用 browse_read）'
        return f"按键失败: ID {element_uuid!r} 不存在。当前已知 ID: {known}"

    label = f"[{element_uuid}] {item['role']} \"{item['name']}\""
    handle = _resolve_element(_page, item)
    if handle is None:
        return f"按键失败: 无法定位元素 {label}"

    try:
        handle.press(key, timeout=_timeout_ms())
        log(f"browser | PRESS {label} key={key!r}")
        refresh_msg = _refresh_item_map()
        return f"已向元素 {label} 发送按键: {key!r}\n{refresh_msg}"
    except Exception as e:
        log(f"browser | PRESS error {label}: {e}")
        return f"按键失败 {label}: {e}"


def browser_find(text: str, max_results: int = 10) -> str:
    """在当前页面中搜索包含指定文字的可见元素。"""
    if _page is None or _page.is_closed():
        return "浏览器尚未打开任何页面。"
    try:
        results = _page.evaluate(
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
            return f"在当前页面中未找到包含 {text!r} 的可见元素。"
        lines = [f"在页面中找到 {len(results)} 处包含 {text!r} 的元素:"]
        for i, r in enumerate(results, 1):
            matched_uuid = next(
                (uid for uid, item in _item_map.items() if text in item['name']),
                None
            )
            uuid_hint = (f"  → UUID: {matched_uuid}" if matched_uuid
                         else "  → 无对应ID，请调用 browse_read 后再交互")
            lines.append(
                f"  [{i}] <{r['tag']}> 选择器: {r['selector']}\n"
                f"      文字: {r['snippet']}\n"
                f"{uuid_hint}"
            )
        log(f"browser | FIND {text!r} → {len(results)} results")
        return "\n".join(lines)
    except Exception as e:
        log(f"browser | FIND error: {e}")
        return f"页面搜索失败: {e}"


def browser_pdf(save_dir: str = ".") -> str:
    """将当前页面打印为 PDF。

    headless 模式：直接调用 page.pdf()。
    有头模式（rebrowser）：通过 CDP Page.printToPDF 命令实现，效果等同。
    """
    if _page is None or _page.is_closed():
        return "浏览器尚未打开任何页面。"
    try:
        import base64
        os.makedirs(save_dir, exist_ok=True)
        filename = os.path.join(save_dir, f"page_{int(time.time())}.pdf")

        if _USING_REBROWSER:
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
        else:
            _page.pdf(path=filename, format="A4", print_background=True)

        size = os.path.getsize(filename)
        log(f"browser | PDF saved to {filename} ({size} bytes)")
        user_log(f"Save PDF: {filename} ({size / 1024:.1f} KB)", role='BROWSER')
        return f"PDF has been saved at: {filename}"
    except Exception as e:
        log(f"browser | PDF error: {e}")
        return f"Failed at generating PDF: {e}"


def browser_wait_for_navigation(timeout: int = None, state: str = "networkidle") -> str:
    """等待页面导航完成。"""
    if _page is None or _page.is_closed():
        return "浏览器尚未打开任何页面。"
    try:
        timeout_ms = (timeout if timeout is not None else (_timeout_ms() // 1000)) * 1000
        _page.wait_for_load_state(state, timeout=timeout_ms)
        log(f"browser | WAIT completed: state={state}")
        return f"页面加载完成（状态：{state}）"
    except Exception as e:
        log(f"browser | WAIT error: {e}")
        return f"等待页面加载失败：{e}"


SEARCH_ENGINES = {
    'google': 'https://www.google.com/search?q=',
    'bing': 'https://www.bing.com/search?q=',
    'baidu': 'https://www.baidu.com/s?wd=',
    'duckduckgo': 'https://duckduckgo.com/?q=',
}


def browser_search(query: str, engine: str = 'google') -> str:
    """使用指定搜索引擎搜索关键词。"""
    from urllib.parse import quote_plus
    engine = engine.lower()
    base_url = SEARCH_ENGINES.get(engine)
    if base_url is None:
        return f"不支持的搜索引擎: {engine!r}。支持: {', '.join(SEARCH_ENGINES)}"
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
        # 给 rebrowser 注入脚本留出稳定窗口，防止后续 evaluate() 报上下文错误
        if _USING_REBROWSER:
            time.sleep(0.5)
        title = page.title()
        return f"已打开页面: {url}\n标题: {title}"
    except Exception as e:
        log(f"browser | SEARCH error: {e}")
        return f"搜索失败: {e}"


def browser_switch(index: int) -> str:
    """切换到指定编号的标签页。"""
    global _page
    try:
        pages = _browser.contexts[0].pages if _browser and _browser.is_connected() else []
        if not pages:
            return "当前没有打开的标签页。"
        if index < 0 or index >= len(pages):
            return f"编号 {index} 超出范围，当前共 {len(pages)} 个标签页（0 ~ {len(pages)-1}）。"
        _page = pages[index]
        _page.bring_to_front()
        log(f"browser | SWITCH → [{index}] {_page.url}")
        return f"已切换到标签页 [{index}]: {_page.title()}  {_page.url}"
    except Exception as e:
        log(f"browser | SWITCH error: {e}")
        return f"切换标签页失败: {e}"


def browser_hover(element_uuid: str) -> str:
    """将鼠标悬停在指定 UUID 对应的元素上，触发 hover 事件（如展开下拉菜单）。"""
    if _page is None or _page.is_closed():
        return "浏览器尚未打开任何页面。"

    item = _item_map.get(element_uuid)
    if item is None:
        known = ', '.join(_item_map.keys()) or '（映射为空，请先调用 browse_read）'
        return f"悬停失败: ID {element_uuid!r} 不存在。当前已知 ID: {known}"

    label = f"[{element_uuid}] {item['role']} \"{item['name']}\""
    handle = _resolve_element(_page, item)
    if handle is None:
        return f"悬停失败: 无法定位元素 {label}"

    try:
        handle.hover(timeout=_timeout_ms())
        log(f"browser | HOVER {label}")
        refresh_msg = _refresh_item_map()
        return f"已悬停在元素: {label}\n{refresh_msg}"
    except Exception as e:
        log(f"browser | HOVER error {label}: {e}")
        return f"悬停失败 {label}: {e}"


def browser_select(element_uuid: str, value: str) -> str:
    """在指定 UUID 对应的 <select> 下拉框中选择选项。

    value 可以是选项的 value 属性、label 文字，或 index（如 "0"、"1"）。
    """
    if _page is None or _page.is_closed():
        return "浏览器尚未打开任何页面。"

    item = _item_map.get(element_uuid)
    if item is None:
        known = ', '.join(_item_map.keys()) or '（映射为空，请先调用 browse_read）'
        return f"选择失败: ID {element_uuid!r} 不存在。当前已知 ID: {known}"

    label = f"[{element_uuid}] {item['role']} \"{item['name']}\""
    handle = _resolve_element(_page, item)
    if handle is None:
        return f"选择失败: 无法定位元素 {label}"

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
        return f"已在 {label} 中选择: {selected}\n{refresh_msg}"
    except Exception:
        # index 匹配失败时回退到按 value 精确匹配
        try:
            selected = handle.select_option(value=value, timeout=_timeout_ms())
            log(f"browser | SELECT (value fallback) {label} → {selected}")
            refresh_msg = _refresh_item_map()
            return f"已在 {label} 中选择: {selected}\n{refresh_msg}"
        except Exception as e:
            log(f"browser | SELECT error {label}: {e}")
            return f"选择失败 {label}: {e}"


def browser_get_url() -> str:
    """返回当前页面的 URL 和标题，用于快速确认页面状态而无需完整读取内容。"""
    if _page is None or _page.is_closed():
        return "浏览器尚未打开任何页面。"
    try:
        url = _page.url
        title = _page.title() or "(无标题)"
        log(f"browser | GET_URL {url}")
        return f"当前页面\n  URL:   {url}\n  标题: {title}"
    except Exception as e:
        log(f"browser | GET_URL error: {e}")
        return f"获取 URL 失败: {e}"


def browser_scroll(direction: str = "down", amount: int = 500,
                   element_uuid: str | None = None) -> str:
    """滚动页面或指定元素。

    Args:
        direction:    滚动方向，'up' / 'down' / 'left' / 'right'，默认 'down'。
        amount:       滚动像素数，默认 500。
        element_uuid: 可选。若传入则滚动该元素内部，否则滚动整个页面。
    """
    if _page is None or _page.is_closed():
        return "浏览器尚未打开任何页面。"

    direction = direction.lower()
    _dir_map = {
        'down':  (0,       amount),
        'up':    (0,      -amount),
        'right': (amount,  0),
        'left':  (-amount, 0),
    }
    if direction not in _dir_map:
        return f"不支持的滚动方向: {direction!r}，请使用 up / down / left / right。"

    delta_x, delta_y = _dir_map[direction]

    try:
        if element_uuid:
            item = _item_map.get(element_uuid)
            if item is None:
                return f"滚动失败: ID {element_uuid!r} 不存在，请先调用 browse_read。"
            handle = _resolve_element(_page, item)
            if handle is None:
                return f"滚动失败: 无法定位元素 [{element_uuid}]"
            handle.evaluate(
                f"el => el.scrollBy({delta_x}, {delta_y})"
            )
            label = f"元素 [{element_uuid}] \"{item['name']}\""
        else:
            _page.evaluate(f"window.scrollBy({delta_x}, {delta_y})")
            label = "页面"

        log(f"browser | SCROLL {label} {direction} {amount}px")
        refresh_msg = _refresh_item_map()
        return f"已向{direction}滚动 {label} {amount}px\n{refresh_msg}"
    except Exception as e:
        log(f"browser | SCROLL error: {e}")
        return f"滚动失败: {e}"


def browser_upload(element_uuid: str, file_paths: list[str] | str) -> str:
    """向指定 UUID 对应的文件选择框（<input type="file">）上传一个或多个本地文件。

    Args:
        element_uuid: browse_read 返回的元素 UUID（role 通常为 button 或直接暴露为 input）。
        file_paths:   本地文件路径，字符串（单文件）或列表（多文件）。
                      路径必须是绝对路径或相对于当前工作目录的路径。
    """
    if _page is None or _page.is_closed():
        return "浏览器尚未打开任何页面。"

    if isinstance(file_paths, str):
        file_paths = [file_paths]

    # 验证文件存在
    missing = [p for p in file_paths if not os.path.isfile(p)]
    if missing:
        return f"上传失败: 以下文件不存在:\n" + "\n".join(f"  {p}" for p in missing)

    item = _item_map.get(element_uuid)
    if item is None:
        known = ', '.join(_item_map.keys()) or '（映射为空，请先调用 browse_read）'
        return f"上传失败: ID {element_uuid!r} 不存在。当前已知 ID: {known}"

    label = f"[{element_uuid}] {item['role']} \"{item['name']}\""

    try:
        # Playwright 推荐用 expect_file_chooser 监听文件对话框
        with _page.expect_file_chooser(timeout=_timeout_ms()) as fc_info:
            handle = _resolve_element(_page, item)
            if handle is None:
                return f"上传失败: 无法定位元素 {label}"
            handle.click(timeout=_timeout_ms())
        fc_info.value.set_files(file_paths)
        names = ", ".join(os.path.basename(p) for p in file_paths)
        log(f"browser | UPLOAD {label} ← {file_paths}")
        refresh_msg = _refresh_item_map()
        return f"已上传 {len(file_paths)} 个文件到 {label}: {names}\n{refresh_msg}"
    except Exception as e:
        # 回退：直接对 input[type=file] 调用 set_input_files
        try:
            handle = _resolve_element(_page, item)
            if handle is None:
                return f"上传失败: 无法定位元素 {label}: {e}"
            handle.set_input_files(file_paths, timeout=_timeout_ms())
            names = ", ".join(os.path.basename(p) for p in file_paths)
            log(f"browser | UPLOAD (set_input_files fallback) {label} ← {file_paths}")
            refresh_msg = _refresh_item_map()
            return f"已上传 {len(file_paths)} 个文件到 {label}: {names}\n{refresh_msg}"
        except Exception as e2:
            log(f"browser | UPLOAD error {label}: {e2}")
            return f"上传失败 {label}: {e2}"


def browser_download(element_uuid: str, save_dir: str = ".") -> str:
    """点击指定 UUID 对应的下载链接/按钮，等待下载完成并将文件保存到指定目录。

    Args:
        element_uuid: browse_read 返回的元素 UUID。
        save_dir:     文件保存目录，默认为当前工作目录。
    """
    if _page is None or _page.is_closed():
        return "浏览器尚未打开任何页面。"

    item = _item_map.get(element_uuid)
    if item is None:
        known = ', '.join(_item_map.keys()) or '（映射为空，请先调用 browse_read）'
        return f"下载失败: ID {element_uuid!r} 不存在。当前已知 ID: {known}"

    label = f"[{element_uuid}] {item['role']} \"{item['name']}\""

    try:
        os.makedirs(save_dir, exist_ok=True)
        download_timeout_ms = get_config().get('wait_download', 60) * 1000
        with _page.expect_download(timeout=download_timeout_ms) as dl_info:
            handle = _resolve_element(_page, item)
            if handle is None:
                return f"下载失败: 无法定位元素 {label}"
            handle.click(timeout=_timeout_ms())
        download = dl_info.value
        suggested = download.suggested_filename or f"download_{int(time.time())}"
        save_path = os.path.join(save_dir, suggested)
        download.save_as(save_path)
        size = os.path.getsize(save_path)
        log(f"browser | DOWNLOAD {label} → {save_path} ({size} bytes)")
        user_log(f"Download: {save_path}（{size / 1024:.1f} KB）", role='BROWSER')
        refresh_msg = _refresh_item_map()
        return f"下载完成: {save_path}（{size / 1024:.1f} KB）\n{refresh_msg}"
    except Exception as e:
        log(f"browser | DOWNLOAD error {label}: {e}")
        return f"下载失败 {label}: {e}"


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
        log("browser | 浏览器已关闭")
        return "浏览器已关闭。"
    except Exception as e:
        log(f"browser | CLOSE error: {e}")
        return f"关闭浏览器时出错：{e}"