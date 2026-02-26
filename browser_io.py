"""
browser_io.py —— 基于 Playwright 的浏览器操作模块。

支持的操作：
    BROWSE_OPEN     打开网页
    BROWSE_READ     读取页面内容（纯文本）
    BROWSE_CLICK    点击元素
    BROWSE_TYPE     在元素中输入文字
    BROWSE_SHOT     截图并返回截图路径
    BROWSE_EVAL     执行 JavaScript
    BROWSE_CLOSE    关闭浏览器
    BROWSE_SELECT   操作下拉框（<select> 元素）
    BROWSE_HOVER    悬停元素（触发 tooltip、下拉菜单等）
    BROWSE_BACK     浏览器后退
    BROWSE_FORWARD  浏览器前进
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

from logger import log, user_log


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
            "Playwright 未安装。请运行：pip install playwright && playwright install chromium"
        )

    if _page is None or _page.is_closed():
        if _browser is None or not _browser.is_connected():
            if _pw is None:
                _pw = sync_playwright().start()
            _browser = _pw.chromium.launch(headless=headless)
        _page = _browser.new_page()
        log("browser_io | 新建浏览器页面")

    return _page


# ── 核心操作函数 ──────────────────────────────────────────────────────

def browser_open(url: str, wait_until: str = "domcontentloaded") -> str:
    """导航到指定 URL，返回页面标题。"""
    page = _ensure_browser()
    log(f"browser_io | OPEN {url}")
    try:
        page.goto(url, wait_until=wait_until, timeout=30_000)
        title = page.title()
        return f"已打开页面：{url}\n标题：{title}"
    except Exception as e:
        log(f"browser_io | OPEN error: {e}")
        return f"打开页面失败：{e}"


def browser_read(max_chars: int = 4000) -> str:
    """返回当前页面的纯文本内容 + 可交互元素清单（截断至 max_chars）。"""
    if _page is None or _page.is_closed():
        return "浏览器尚未打开任何页面，请先使用 BROWSE_OPEN。"
    try:
        # 第一份：纯文本（去除 script/style/noscript/svg）
        text = _page.inner_text("body")
        text = "\n".join(line.strip() for line in text.splitlines() if line.strip())
        if len(text) > max_chars:
            text = text[:max_chars] + f"\n…（内容已截断，共 {len(text)} 字符）"

        # 第二份：可交互元素清单
        elements = _page.evaluate("""() => {
            return [...document.querySelectorAll('input, button, a, select, textarea')]
                .filter(el => el.offsetParent !== null)
                .slice(0, 50)
                .map(el => {
                    const tag = el.tagName.toLowerCase();
                    const id = el.id ? '#' + el.id : '';
                    const cls = (el.className && typeof el.className === 'string')
                        ? '.' + el.className.trim().split(/\\s+/)[0] : '';
                    const selector = id || cls || tag;
                    const label = (el.innerText || '').slice(0, 20)
                        || (el.value || '').slice(0, 20)
                        || (el.placeholder || '').slice(0, 20);
                    const type = el.type || '';
                    return '[' + tag + '] ' + selector + ' | type=' + type + ' | "' + label + '"';
                })
                .join('\\n');
        }""")

        return (
            f"<当前页面：{_page.url}>\n\n"
            f"<── 页面文字内容 ──>\n{text}\n\n"
            f"<── 可交互元素 ──>\n{elements}"
        )
    except Exception as e:
        log(f"browser_io | READ error: {e}")
        return f"读取页面内容失败：{e}"


def browser_click(selector: str) -> str:
    """点击与 CSS/XPath 选择器匹配的元素。"""
    if _page is None or _page.is_closed():
        return "浏览器尚未打开任何页面。"
    try:
        _page.click(selector, timeout=10_000)
        time.sleep(0.5)
        log(f"browser_io | CLICK {selector}")
        return f"已点击元素：{selector}"
    except Exception as e:
        log(f"browser_io | CLICK error: {e}")
        return f"点击元素失败（{selector}）：{e}"


def browser_type(selector: str, text: str, clear: bool = True) -> str:
    """在指定元素中输入文字（默认先清空）。"""
    if _page is None or _page.is_closed():
        return "浏览器尚未打开任何页面。"
    try:
        _page.click(selector, timeout=10_000)
        if clear:
            _page.fill(selector, "")
        _page.type(selector, text, delay=30)
        log(f"browser_io | TYPE {selector} <- {text!r}")
        return f"已在 {selector} 中输入：{text}"
    except Exception as e:
        log(f"browser_io | TYPE error: {e}")
        return f"输入文字失败（{selector}）：{e}"


def browser_screenshot(save_dir: str = ".") -> str:
    """截取当前页面截图，返回保存路径。"""
    if _page is None or _page.is_closed():
        return "浏览器尚未打开任何页面。"
    try:
        os.makedirs(save_dir, exist_ok=True)
        filename = os.path.join(save_dir, f"screenshot_{int(time.time())}.png")
        _page.screenshot(path=filename, full_page=True)
        log(f"browser_io | SHOT saved to {filename}")
        user_log(f"截图已保存：{filename}", role='BROWSER')
        return f"截图已保存：{filename}"
    except Exception as e:
        log(f"browser_io | SHOT error: {e}")
        return f"截图失败：{e}"


def browser_eval(script: str) -> str:
    """在当前页面执行 JavaScript，返回结果字符串。"""
    if _page is None or _page.is_closed():
        return "浏览器尚未打开任何页面。"
    try:
        result = _page.evaluate(script)
        log(f"browser_io | EVAL result: {result}")
        return f"JavaScript 执行结果：{result}"
    except Exception as e:
        log(f"browser_io | EVAL error: {e}")
        return f"JavaScript 执行失败：{e}"


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
        log("browser_io | 浏览器已关闭")
        return "浏览器已关闭。"
    except Exception as e:
        log(f"browser_io | CLOSE error: {e}")
        return f"关闭浏览器时出错：{e}"


def browser_select(selector: str, value: str) -> str:
    """
    操作 <select> 下拉框，按 value → label → index 顺序尝试匹配。
    返回实际选中的选项文字。
    """
    if _page is None or _page.is_closed():
        return "浏览器尚未打开任何页面。"
    try:
        selected = None
        for method, kw in [
            ("value", {"value": value}),
            ("label", {"label": value}),
            ("index", {"index": int(value)} if value.lstrip('-').isdigit() else None),
        ]:
            if kw is None:
                continue
            try:
                result = _page.select_option(selector, timeout=5_000, **kw)
                selected = result
                log(f"browser_io | SELECT {selector} by {method}={value!r} → {result}")
                break
            except Exception:
                continue
        if selected is None:
            return f"下拉框选择失败：在 {selector} 中未找到选项 {value!r}（已尝试 value / label / index）。"
        label = _page.evaluate(
            f"() => {{ const el = document.querySelector({selector!r}); "
            f"return el ? el.options[el.selectedIndex].text : null; }}"
        )
        return f"已选择下拉框 {selector} 的选项：{label or selected}"
    except Exception as e:
        log(f"browser_io | SELECT error: {e}")
        return f"下拉框操作失败（{selector}）：{e}"


def browser_hover(selector: str) -> str:
    """将鼠标悬停在指定元素上，触发 :hover 样式及相关事件。"""
    if _page is None or _page.is_closed():
        return "浏览器尚未打开任何页面。"
    try:
        _page.hover(selector, timeout=10_000)
        time.sleep(0.4)
        log(f"browser_io | HOVER {selector}")
        return f"已悬停元素：{selector}"
    except Exception as e:
        log(f"browser_io | HOVER error: {e}")
        return f"悬停元素失败（{selector}）：{e}"


def browser_back() -> str:
    """浏览器后退一页。"""
    if _page is None or _page.is_closed():
        return "浏览器尚未打开任何页面。"
    try:
        _page.go_back(timeout=15_000, wait_until="domcontentloaded")
        log(f"browser_io | BACK → {_page.url}")
        return f"已后退，当前页面：{_page.url}"
    except Exception as e:
        log(f"browser_io | BACK error: {e}")
        return f"后退失败：{e}"


def browser_forward() -> str:
    """浏览器前进一页。"""
    if _page is None or _page.is_closed():
        return "浏览器尚未打开任何页面。"
    try:
        _page.go_forward(timeout=15_000, wait_until="domcontentloaded")
        log(f"browser_io | FORWARD → {_page.url}")
        return f"已前进，当前页面：{_page.url}"
    except Exception as e:
        log(f"browser_io | FORWARD error: {e}")
        return f"前进失败：{e}"


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
        lines = [f"在页面中找到 {len(results)} 处包含 {text!r} 的元素："]
        for i, r in enumerate(results, 1):
            lines.append(f"  [{i}] <{r['tag']}> 选择器：{r['selector']}\n      文字：{r['snippet']}")
        log(f"browser_io | FIND {text!r} → {len(results)} results")
        return "\n".join(lines)
    except Exception as e:
        log(f"browser_io | FIND error: {e}")
        return f"页面搜索失败：{e}"


def browser_download(url: str, save_dir: str = ".") -> str:
    """
    下载指定 URL 的文件到 save_dir 目录。
    通过 Playwright 下载事件拦截，保留当前页面登录态 Cookie。
    """
    if _page is None or _page.is_closed():
        return "浏览器尚未打开任何页面。"
    try:
        os.makedirs(save_dir, exist_ok=True)
        with _page.expect_download(timeout=60_000) as dl_info:
            _page.evaluate(f"() => {{ window.location.href = {url!r}; }}")
        download = dl_info.value
        suggested = download.suggested_filename or f"download_{int(time.time())}"
        save_path = os.path.join(save_dir, suggested)
        download.save_as(save_path)
        log(f"browser_io | DOWNLOAD saved to {save_path}")
        user_log(f"文件已下载：{save_path}", role='BROWSER')
        return f"文件已下载并保存至：{save_path}"
    except Exception as e:
        log(f"browser_io | DOWNLOAD error: {e}")
        return f"下载失败：{e}"


def browser_upload(selector: str, file_path: str) -> str:
    """向 <input type="file"> 元素上传本地文件。"""
    if _page is None or _page.is_closed():
        return "浏览器尚未打开任何页面。"
    if not os.path.isfile(file_path):
        return f"上传失败：本地文件不存在：{file_path}"
    try:
        _page.set_input_files(selector, file_path, timeout=10_000)
        log(f"browser_io | UPLOAD {file_path} → {selector}")
        return f"已将文件 {file_path} 上传至输入框 {selector}。"
    except Exception as e:
        log(f"browser_io | UPLOAD error: {e}")
        return f"上传失败（{selector}）：{e}"


def browser_pdf(save_dir: str = ".") -> str:
    """将当前页面打印为 PDF（仅 headless 模式支持）并保存到 save_dir。"""
    if _page is None or _page.is_closed():
        return "浏览器尚未打开任何页面。"
    try:
        os.makedirs(save_dir, exist_ok=True)
        filename = os.path.join(save_dir, f"page_{int(time.time())}.pdf")
        _page.pdf(path=filename, format="A4", print_background=True)
        log(f"browser_io | PDF saved to {filename}")
        user_log(f"PDF 已保存：{filename}", role='BROWSER')
        return f"PDF 已保存至：{filename}"
    except Exception as e:
        log(f"browser_io | PDF error: {e}")
        return f"PDF 生成失败（注意：仅 headless 模式支持此功能）：{e}"


# ── 安全接口（bot_io 中应调用这些）──────────────────────────────────────
#
# Playwright sync_api 强制要求所有 Page 操作在创建它的同一线程中执行。
# 使用 ThreadPoolExecutor 会导致 "cannot switch to a different thread" 错误。
# 因此这里直接调用，不做线程包装，超时由各函数内部的 Playwright timeout 参数控制。

def browser_open_safe(url: str, wait_until: str = "domcontentloaded") -> str:
    try:
        return browser_open(url, wait_until)
    except Exception as e:
        log(f"browser_io | browser_open_safe error: {e}")
        return str(e)


def browser_read_safe(max_chars: int = 4000) -> str:
    try:
        return browser_read(max_chars)
    except Exception as e:
        log(f"browser_io | browser_read_safe error: {e}")
        return str(e)


def browser_click_safe(selector: str) -> str:
    try:
        return browser_click(selector)
    except Exception as e:
        log(f"browser_io | browser_click_safe error: {e}")
        return str(e)

def browser_type_safe(selector: str, text: str, clear: bool = True) -> str:
    try:
        return browser_type(selector, text, clear)
    except Exception as e:
        log(f"browser_io | browser_type_safe error: {e}")
        return str(e)

def browser_screenshot_safe(save_dir: str = ".") -> str:
    try:
        return browser_screenshot(save_dir)
    except Exception as e:
        log(f"browser_io | browser_screenshot_safe error: {e}")
        return str(e)

def browser_eval_safe(script: str) -> str:
    try:
        return browser_eval(script)
    except Exception as e:
        log(f"browser_io | browser_eval_safe error: {e}")
        return str(e)

def browser_close_safe() -> str:
    try:
        return browser_close()
    except Exception as e:
        log(f"browser_io | browser_close_safe error: {e}")
        return str(e)

def browser_select_safe(selector: str, value: str) -> str:
    try:
        return browser_select(selector, value)
    except Exception as e:
        log(f"browser_io | browser_select_safe error: {e}")
        return str(e)

def browser_hover_safe(selector: str) -> str:
    try:
        return browser_hover(selector)
    except Exception as e:
        log(f"browser_io | browser_hover_safe error: {e}")
        return str(e)

def browser_back_safe() -> str:
    try:
        return browser_back()
    except Exception as e:
        log(f"browser_io | browser_back_safe error: {e}")
        return str(e)

def browser_forward_safe() -> str:
    try:
        return browser_forward()
    except Exception as e:
        log(f"browser_io | browser_forward_safe error: {e}")
        return str(e)

def browser_find_safe(text: str, max_results: int = 10) -> str:
    try:
        return browser_find(text, max_results)
    except Exception as e:
        log(f"browser_io | browser_find_safe error: {e}")
        return str(e)

def browser_download_safe(url: str, save_dir: str = ".") -> str:
    try:
        return browser_download(url, save_dir)
    except Exception as e:
        log(f"browser_io | browser_download_safe error: {e}")
        return str(e)

def browser_upload_safe(selector: str, file_path: str) -> str:
    try:
        return browser_upload(selector, file_path)
    except Exception as e:
        log(f"browser_io | browser_upload_safe error: {e}")
        return str(e)

def browser_pdf_safe(save_dir: str = ".") -> str:
    try:
        return browser_pdf(save_dir)
    except Exception as e:
        log(f"browser_io | browser_pdf_safe error: {e}")
        return str(e)