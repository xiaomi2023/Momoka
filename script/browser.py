"""
browser.py —— 基于 Playwright 的浏览器操作模块。

支持的操作：
    BROWSE_OPEN     打开网页
    BROWSE_READ     读取页面内容（纯文本）
    BROWSE_EVAL     执行 JavaScript
    BROWSE_CLOSE    关闭浏览器
    BROWSE_FIND     在页面中搜索文字，返回匹配元素信息
    BROWSE_DOWNLOAD 下载文件到工作目录
    BROWSE_UPLOAD   向文件输入框上传本地文件
    BROWSE_PDF      将当前页面打印为 PDF 并保存

安装依赖：
    pip install playwright
    playwright install chromium

线程说明：
    Playwright sync_api 要求所有操作在同一线程执行，不支持跨线程共享 Page。
    因此本模块所有函数均在调用方线程中直接执行，依赖 Playwright 内置 timeout 参数
    作为超时防线，不使用 ThreadPoolExecutor 包装。
"""

from __future__ import annotations

import os
import time
from typing import Optional

from script.logger import log, user_log


def _timeout_ms() -> int:
    """从运行时配置读取超时时长（秒），转换为毫秒供 Playwright 使用。"""
    try:
        from config import get_config
        return get_config().get('wait', 10) * 1000
    except Exception:
        return 10_000


# ── 延迟导入 Playwright，避免未安装时整体崩溃 ─────────────────────────
try:
    from playwright.sync_api import sync_playwright, Page, Browser, Playwright

    _PLAYWRIGHT_AVAILABLE = True
except ImportError:
    _PLAYWRIGHT_AVAILABLE = False

# ── 全局单例 ─────────────────────────────────────────────────────────
_pw: Optional["Playwright"] = None
_browser: Optional["Browser"] = None
_page: Optional["Page"] = None


def _ensure_browser(headless: bool = True) -> "Page":
    """确保浏览器已启动，返回当前 Page。"""
    global _pw, _browser, _page

    if not _PLAYWRIGHT_AVAILABLE:
        raise RuntimeError(
            "Playwright 未安装。请运行: pip install playwright && playwright install chromium"
        )

    if _page is None or _page.is_closed():
        if _browser is None or not _browser.is_connected():
            if _pw is None:
                _pw = sync_playwright().start()
            _browser = _pw.chromium.launch(headless=headless)
        _page = _browser.new_page()
        log("browser | 新建浏览器页面")

    return _page


# ── 核心操作函数 ──────────────────────────────────────────────────────

def browser_open(url: str, wait_until: str = "domcontentloaded") -> str:
    """导航到指定 URL，返回页面标题。"""
    page = _ensure_browser()
    log(f"browser | OPEN {url}")
    try:
        page.goto(url, wait_until=wait_until, timeout=_timeout_ms())
        title = page.title()
        return f"已打开页面: {url}\n标题: {title}"
    except Exception as e:
        log(f"browser | OPEN error: {e}")
        return f"打开页面失败: {e}"


def _get_tabs_info() -> str:
    """返回当前所有标签页的编号、URL、标题列表字符串。"""
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


def browser_read(max_chars: int = 4000) -> str:
    """返回当前页面的内容，可交互元素以 [INTERACTIVE] 标记内联嵌入文字流中。
    若检测到有新标签页打开，自动切换到最新标签页再读取。
    """
    global _page
    if _page is None or _page.is_closed():
        return "浏览器尚未打开任何页面，请先使用 BROWSE_OPEN。"

    # ── 检测新标签页 ──────────────────────────────────────────────────
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

    try:
        # 通过 JS 遍历 DOM，将文字节点和可交互元素按文档顺序合并输出
        raw = _page.evaluate("""() => {
            const lines = [];
            const interactive = new Set(['INPUT','BUTTON','A','SELECT','TEXTAREA']);

            function isVisible(el) {
                return el.offsetParent !== null || el.tagName === 'BODY';
            }

            function getSelector(el) {
                if (el.id) return '#' + el.id;
                if (el.className && typeof el.className === 'string') {
                    const cls = el.className.trim().split(/\\s+/)[0];
                    if (cls) return el.tagName.toLowerCase() + '.' + cls;
                }
                return el.tagName.toLowerCase();
            }

            function visit(node) {
                if (node.nodeType === Node.TEXT_NODE) {
                    const t = node.textContent.trim();
                    if (t) lines.push(t);
                    return;
                }
                if (node.nodeType !== Node.ELEMENT_NODE) return;
                const tag = node.tagName;
                if (['SCRIPT','STYLE','NOSCRIPT','SVG'].includes(tag)) return;

                if (interactive.has(tag) && isVisible(node)) {
                    let label = (node.innerText || '').trim().slice(0, 30)
                             || (node.value || '').slice(0, 30)
                             || (node.placeholder || '').slice(0, 30)
                             || '';
                    // 如果标签是 A 且 label 为空，则跳过（不生成交互条目）
                    if (tag === 'A' && !label) return;

                    const sel = getSelector(node);
                    const type = node.type || '';
                    const typeStr = type ? ' type=' + type : '';
                    const marker = '[INTERACTIVE|' + tag.toLowerCase() + '|' + sel + typeStr + '|"' + label + '"]';
                    // 内联追加到上一行，若无上一行则新起一行
                    if (lines.length > 0) {
                        lines[lines.length - 1] += ' ' + marker;
                    } else {
                        lines.push(marker);
                    }
                    return;  // 不递归进交互元素内部
                }

                for (const child of node.childNodes) visit(child);
            }

            visit(document.body);
            return lines.join('\\n');
        }""")

        # 去除空行、截断
        text = "\n".join(line for line in raw.splitlines() if line.strip())
        if len(text) > max_chars:
            text = text[:max_chars] + (f"\n…（内容已截断，共 {len(text)} 字符。"
                                       f"如需阅读更多内容，可以在调用时添加max_chars参数指定最大读取字数）")

        tabs_info = _get_tabs_info()
        return (
                f"<当前页面: {_page.url}>\n"
                f"<说明: [INTERACTIVE|标签|选择器|文字] 为可交互元素，可用选择器对其进行操作>\n"
                + (f"{tabs_info}\n" if tabs_info else "")
                + f"\n{text}"
        )
    except Exception as e:
        log(f"browser | READ error: {e}")
        return f"读取页面内容失败: {e}"


def browser_eval(script: str) -> str:
    """在当前页面执行 JavaScript，返回结果字符串。"""
    if _page is None or _page.is_closed():
        return "浏览器尚未打开任何页面。"
    try:
        result = _page.evaluate(script)
        _page.wait_for_load_state("networkidle", timeout=_timeout_ms())
        log(f"browser | EVAL result: {result}")
        base_msg = f"JavaScript 执行结果: {result}"
        # 检测常见的异步关键词
        async_keywords = ['setTimeout', 'setInterval', 'Promise', 'async', 'await']
        if any(keyword in script for keyword in async_keywords):
            base_msg += ("\n<警告: 检测到脚本中可能包含异步操作。异步操作可能不会在 evaluate 返回前完成，"
                         "若需触发导航，建议调用 browse_wait_for_navigation 等待，或使用同步方式编写脚本。>")
        return base_msg
    except Exception as e:
        log(f"browser | EVAL error: {e}")
        err_msg = f"JavaScript 执行失败: {e}"
        if "return" in script:
            err_msg += "\n<警告: 检测到 JavaScript 表达式中可能包含了 return 语句。表达式在全局作用域下执行，请不要非法使用 return 。>"
        return err_msg


def browser_find(text: str, max_results: int = 10) -> str:
    """
    在当前页面中搜索包含指定文字的可见元素，
    返回每个匹配元素的标签名、推断的 CSS 选择器及文字片段。
    """
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
        lines = [f"在页面中找到 {len(results)} 处包含 {text!r} 的元素: "]
        for i, r in enumerate(results, 1):
            lines.append(f"  [{i}] <{r['tag']}> 选择器: {r['selector']}\n      文字: {r['snippet']}")
        log(f"browser | FIND {text!r} → {len(results)} results")
        return "\n".join(lines)
    except Exception as e:
        log(f"browser | FIND error: {e}")
        return f"页面搜索失败: {e}"


def browser_download(url: str, save_dir: str = ".") -> str:
    """
    下载指定 URL 的文件到 save_dir 目录。
    通过 Playwright 下载事件拦截，保留当前页面登录态 Cookie。
    """
    if _page is None or _page.is_closed():
        return "浏览器尚未打开任何页面。"
    try:
        os.makedirs(save_dir, exist_ok=True)
        with _page.expect_download(timeout=_timeout_ms()) as dl_info:
            _page.evaluate(f"() => {{ window.location.href = {url!r}; }}")
        download = dl_info.value
        suggested = download.suggested_filename or f"download_{int(time.time())}"
        save_path = os.path.join(save_dir, suggested)
        download.save_as(save_path)
        log(f"browser | DOWNLOAD saved to {save_path}")
        user_log(f"文件已下载: {save_path}", role='BROWSER')
        return f"文件已下载并保存至: {save_path}"
    except Exception as e:
        log(f"browser | DOWNLOAD error: {e}")
        return f"下载失败: {e}"


def browser_upload(selector: str, file_path: str) -> str:
    """向 <input type="file"> 元素上传本地文件。"""
    if _page is None or _page.is_closed():
        return "浏览器尚未打开任何页面。"
    if not os.path.isfile(file_path):
        return f"上传失败: 本地文件不存在: {file_path}"
    try:
        _page.set_input_files(selector, file_path, timeout=_timeout_ms())
        log(f"browser | UPLOAD {file_path} → {selector}")
        return f"已将文件 {file_path} 上传至输入框 {selector}。"
    except Exception as e:
        log(f"browser | UPLOAD error: {e}")
        return f"上传失败（{selector}）: {e}"


def browser_pdf(save_dir: str = ".") -> str:
    """将当前页面打印为 PDF（仅 headless 模式支持）并保存到 save_dir。"""
    if _page is None or _page.is_closed():
        return "浏览器尚未打开任何页面。"
    try:
        os.makedirs(save_dir, exist_ok=True)
        filename = os.path.join(save_dir, f"page_{int(time.time())}.pdf")
        _page.pdf(path=filename, format="A4", print_background=True)
        log(f"browser | PDF saved to {filename}")
        user_log(f"PDF 已保存: {filename}", role='BROWSER')
        return f"PDF 已保存至: {filename}"
    except Exception as e:
        log(f"browser | PDF error: {e}")
        return f"PDF 生成失败: {e}"


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
    """使用指定搜索引擎搜索关键词，直接跳转到搜索结果页。"""
    from urllib.parse import quote_plus
    engine = engine.lower()
    base_url = SEARCH_ENGINES.get(engine)
    if base_url is None:
        supported = ', '.join(SEARCH_ENGINES.keys())
        return f"不支持的搜索引擎: {engine!r}。支持的引擎: {supported}"
    url = base_url + quote_plus(query)
    log(f"browser | SEARCH [{engine}] {query!r} → {url}")
    return browser_open(url)


def browser_switch(index: int) -> str:
    """切换到指定编号的标签页。"""
    global _page
    try:
        pages = _browser.contexts[0].pages if _browser and _browser.is_connected() else []
        if not pages:
            return "当前没有打开的标签页。"
        if index < 0 or index >= len(pages):
            return f"编号 {index} 超出范围，当前共有 {len(pages)} 个标签页（0 ~ {len(pages) - 1}）。"
        _page = pages[index]
        _page.bring_to_front()
        log(f"browser | SWITCH → [{index}] {_page.url}")
        return f"已切换到标签页 [{index}]: {_page.title()}  {_page.url}"
    except Exception as e:
        log(f"browser | SWITCH error: {e}")
        return f"切换标签页失败: {e}"


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
        log("browser | 浏览器已关闭")
        return "浏览器已关闭。"
    except Exception as e:
        log(f"browser | CLOSE error: {e}")
        return f"关闭浏览器时出错：{e}"