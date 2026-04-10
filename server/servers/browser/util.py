"""
server/servers/browser/util.py —— 浏览器工具辅助函数和常量。

包含：
- JS 代码加载
- 超时配置读取
- UUID 生成
- 安全的 page.evaluate() 封装（带重试）
- 搜索引擎配置
- Playwright 启动参数
"""

from __future__ import annotations

import hashlib
import time
from functools import lru_cache
from pathlib import Path
from typing import Optional

from logger import log


# ── JavaScript 代码加载 ─────────────────────────────────────────────────────

@lru_cache(maxsize=None)
def _load_js(filename: str) -> str:
    """加载指定名称的 JavaScript 文件内容（带缓存）。

    Args:
        filename: JS 文件名（不含路径）
    Returns:
        JS 代码字符串
    """
    script_dir = Path(__file__).parent / 'scripts'
    js_path = script_dir / filename
    try:
        return js_path.read_text(encoding='utf-8')
    except Exception as e:
        log(f"browser | Failed to load JS file {filename}: {e}")
        raise


# ── 超时配置 ─────────────────────────────────────────────────────────────

def _timeout_ms() -> int:
    """从配置中读取超时时间，转换为毫秒。"""
    try:
        from config import get_config
        return get_config().get('wait', 10) * 1000
    except Exception:
        return 10_000


# ── UUID 生成 ────────────────────────────────────────────────────────────

def _make_uid(role: str, locator_name: str, index: int, seen: set) -> str:
    """基于 role + locator_name + index 生成稳定的 6 位 16 进制 ID，碰撞时加后缀。"""
    raw = hashlib.md5(f"{role}|{locator_name}|{index}".encode()).hexdigest()[:6]
    uid = raw
    while uid in seen:
        uid += "x"
    seen.add(uid)
    return uid


# ── 安全的 evaluate 封装 ─────────────────────────────────────────────────

_CONTEXT_ERR = "Cannot find context with specified id"


def _safe_evaluate(page, script, arg=None, *, retries: int = 4,
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


# ── 常量配置 ─────────────────────────────────────────────────────────────

# 可交互 role 列表（顺序决定枚举优先级）
_INTERACTIVE_ROLES: list[str] = [
    'button', 'link', 'textbox', 'searchbox', 'combobox',
    'checkbox', 'radio', 'menuitem', 'menuitemcheckbox', 'menuitemradio',
    'option', 'switch', 'tab', 'slider', 'spinbutton',
    'listbox', 'treeitem', 'gridcell',
]
_INTERACTIVE_ROLES_SET = set(_INTERACTIVE_ROLES)

# 搜索引擎配置
SEARCH_ENGINES = {
    'google': 'https://www.google.com/search?q=',
    'bing': 'https://www.bing.com/search?q=',
    'baidu': 'https://www.baidu.com/s?wd=',
    'duckduckgo': 'https://duckduckgo.com/?q=',
}

# Playwright 浏览器启动参数
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
