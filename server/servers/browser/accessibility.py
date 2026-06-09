"""
server/servers/browser/accessibility.py —— 无障碍树解析与元素定位。

包含：
- 无障碍树解析（_parse_ax_tree）
- 元素精确定位（_resolve_element）
- 元素映射刷新（_refresh_item_map）

使用 rebrowser-playwright 异步 API，通过 browser_state 的后台事件循环运行。
"""

from __future__ import annotations

import asyncio
import time
from typing import Optional

from rebrowser_playwright.async_api import Page

from logger import log
from server.servers.browser.util import (
    _load_js,
    _async_safe_evaluate,
    _make_uid,
    _INTERACTIVE_ROLES,
    _timeout_ms,
)
from server.servers.browser.browser_state import (
    get_page,
    get_item_map,
    set_item_map,
    _maybe_switch_to_new_tab,
    _run_async,
)


async def _async_parse_ax_tree(page: "Page") -> tuple[list[str], list[dict]]:
    """异步：用 locator 查询页面，返回 (text_lines, interactive_items)。

    text_lines:        页面正文文字行列表（过滤空行，支持 Markdown 格式）
    interactive_items: list of {uuid, role, name, locator_index, ...}
        - uuid:           6 位唯一 ID
        - role:           小写 role 字符串
        - name:           可访问名称（已保证非空）
        - locator_index:  该 role+name 组合下的第几个元素（0-based，用于精确定位）
        - href:           链接的绝对 URL（仅 link 角色）
        - action:         按钮的表单动作（仅 button 角色）
        - field_label:    输入框的标签文字（仅 input 类角色）
    """
    text_lines: list[str] = []
    interactive_items: list[dict] = []

    # ── 正文：通过 JS 遍历可见文字节点 ──────────────────────────────────
    _js_text = _load_js('extract_text.js')
    try:
        raw_text = await _async_safe_evaluate(page, _js_text)
        text_lines = [t for t in (raw_text or []) if t.strip()]
    except Exception as e:
        log(f"browser | text extraction error: {e}")

    # ── 可交互元素：按 role 逐一查询 ───────────────────────────────────
    seen_uids: set = set()
    for role in _INTERACTIVE_ROLES:
        try:
            locator = page.get_by_role(role)
            count = await locator.count()
            if count == 0:
                continue
            for i in range(count):
                el = locator.nth(i)
                try:
                    _input_roles = {'textbox', 'searchbox', 'combobox', 'spinbutton'}
                    if role in _input_roles:
                        locator_name = (await el.get_attribute('placeholder') or '').strip()
                        if not locator_name:
                            locator_name = (await el.get_attribute('aria-label') or '').strip()
                        if not locator_name:
                            locator_name = (await el.get_attribute('title') or '').strip()
                        name = locator_name
                    else:
                        locator_name = (await el.inner_text(timeout=500) or '').strip()
                        if not locator_name:
                            locator_name = (await el.get_attribute('aria-label') or '').strip()
                        if not locator_name:
                            locator_name = (await el.get_attribute('placeholder') or '').strip()
                        if not locator_name:
                            locator_name = (await el.get_attribute('title') or '').strip()
                        if not locator_name:
                            locator_name = (await el.get_attribute('value') or '').strip()
                        name = locator_name
                except Exception:
                    name = ''
                    locator_name = ''

                if not locator_name:
                    continue

                if not name:
                    name = locator_name

                try:
                    visible = await el.is_visible()
                except Exception:
                    visible = False

                try:
                    disabled = await el.is_disabled()
                except Exception:
                    disabled = False

                uid = _make_uid(role, locator_name, i, seen_uids)

                # 构建扩展属性
                extra_attrs = {}
                if disabled:
                    extra_attrs['disabled'] = True

                # 按钮：提取 pressed/expanded 状态
                if role == 'button':
                    try:
                        action = (await el.get_attribute('aria-pressed') or
                                 await el.get_attribute('aria-expanded') or '')
                        if action:
                            extra_attrs['state'] = action
                    except Exception:
                        pass

                # 输入框：提取字段标签和当前填充值
                elif role in {'textbox', 'searchbox', 'combobox', 'spinbutton'}:
                    try:
                        field_id = (await el.get_attribute('id') or '').strip()
                        if field_id:
                            try:
                                label_el = page.locator(f'label[for="{field_id}"]')
                                if await label_el.count() > 0:
                                    extra_attrs['field_label'] = (await label_el.inner_text(timeout=500) or '').strip()
                            except Exception:
                                pass
                        current_val = (await el.input_value(timeout=500) or '').strip()
                        if current_val:
                            extra_attrs['fill'] = current_val
                        input_type = (await el.get_attribute('type') or 'text').strip()
                        if input_type != 'text':
                            extra_attrs['input_type'] = input_type
                    except Exception:
                        pass

                # 复选框/单选框：提取选中状态
                elif role in {'checkbox', 'radio'}:
                    try:
                        checked = await el.get_attribute('aria-checked')
                        if checked is None and hasattr(el, 'is_checked'):
                            checked = await el.is_checked()
                        extra_attrs['checked'] = str(checked) == 'true' or checked is True
                    except Exception:
                        pass

                interactive_items.append({
                    'uuid': uid,
                    'role': role,
                    'name': name,
                    'locator_name': locator_name,
                    'locator_index': i,
                    'visible': visible,
                    **extra_attrs,
                })
        except Exception as e:
            log(f"browser | role={role} query error: {e}")

    return text_lines, interactive_items


async def _async_resolve_element(page: "Page", item: dict) -> Optional[object]:
    """异步：根据 role + locator_name 精确定位 ElementHandle。

    定位策略（按优先级）：
      1. get_by_role(role, name=name, exact=True)
      2. [仅 input 类] get_by_placeholder(name)
      3. [仅 input 类] get_by_label(name)
      4. [仅 input 类] CSS [id=...] / [name=...]
      5. get_by_text(name, exact=True)
    """
    role = item['role']
    name = item.get('locator_name') or item['name']
    idx = item.get('locator_index', 0)
    _input_roles = {'textbox', 'searchbox', 'combobox', 'spinbutton'}

    async def _first_visible(locator) -> Optional[object]:
        """从 locator 中取第一个可见 ElementHandle。"""
        try:
            count = await locator.count()
        except Exception:
            return None
        if count == 0:
            return None
        for i in range(count):
            try:
                handle = await locator.nth(i).element_handle(timeout=1000)
                if handle and await handle.is_visible():
                    if i != idx:
                        log(f"browser | _resolve_element skipped invisible nth({idx}), using nth({i})")
                    return handle
            except Exception:
                continue
        try:
            return await locator.nth(idx).element_handle(timeout=3000)
        except Exception as e:
            log(f"browser | _resolve_element nth({idx}) fallback error: {e}")
        return None

    # ── 策略 1：get_by_role ───────────────────────────────────────────────
    try:
        h = await _first_visible(page.get_by_role(role, name=name, exact=True))
        if h:
            return h
    except Exception as e:
        log(f"browser | _resolve_element get_by_role error role={role} name={name!r}: {e}")

    # ── 策略 2 & 3 & 4：仅 input 类元素 ───────────────────────────────────
    if role in _input_roles:
        # 2. placeholder 精确匹配
        try:
            h = await _first_visible(page.get_by_placeholder(name, exact=True))
            if h:
                log(f"browser | _resolve_element hit placeholder {name!r}")
                return h
        except Exception:
            pass

        # 3. 关联 label 文字
        try:
            h = await _first_visible(page.get_by_label(name, exact=True))
            if h:
                log(f"browser | _resolve_element hit label {name!r}")
                return h
        except Exception:
            pass

        # 4. CSS 属性
        for attr in ('placeholder', 'aria-label', 'name'):
            try:
                sel = f'[{attr}="{name}"]'
                locator = page.locator(sel)
                h = await _first_visible(locator)
                if h:
                    log(f"browser | _resolve_element hit css {sel}")
                    return h
            except Exception:
                continue

    # ── 策略 5：按可见文字兜底 ────────────────────────────────────────────
    try:
        h = await _first_visible(page.get_by_text(name, exact=True))
        if h:
            return h
    except Exception as e:
        log(f"browser | _resolve_element get_by_text error name={name!r}: {e}")

    return None


async def _async_refresh_item_map() -> str:
    """异步：等待页面稳定后重建 UUID 映射。"""
    from server.servers.browser.browser_state import _async_maybe_switch_to_new_tab
    await _async_maybe_switch_to_new_tab()
    page = get_page()
    if page is None:
        return "<Page is not available>"

    try:
        await page.wait_for_load_state("domcontentloaded", timeout=_timeout_ms())
    except Exception:
        pass
    try:
        await page.wait_for_load_state("networkidle", timeout=3000)
    except Exception:
        pass
    await asyncio.sleep(0.3)

    old_map = get_item_map()
    _, interactive_items = await _async_parse_ax_tree(page)
    new_map = {item['uuid']: item for item in interactive_items}
    set_item_map(new_map)
    log(f"browser | _refresh_item_map → {len(new_map)} interactive elements")

    added = {uid: item for uid, item in new_map.items() if uid not in old_map}
    removed = {uid: item for uid, item in old_map.items() if uid not in new_map}

    parts = ["<The page has been refreshed. Consider using browser_read to get the latest information>"]
    if added:
        lines = []
        for uid, item in added.items():
            extra = ''
            if item.get('field_label'):
                extra = f'  [Label: {item["field_label"]}]'
            elif 'checked' in item:
                extra = f'  [Checked: {item["checked"]}]'
            lines.append(f"  [{uid}] {item['role']}  {item['name']}{extra}")
        parts.append("<New Items>\n" + "\n".join(lines) + "\n</New Items>")
    if removed:
        lines = [f"  [{uid}] {item['role']}  {item['name']}" for uid, item in removed.items()]
        parts.append("<Missing Items>\n" + "\n".join(lines) + "\n</Missing Items>")
    if not added and not removed:
        parts.append("<Item list has not changed>")

    return "\n".join(parts)


# ── 同步包装接口（供 browser.py 调用） ─────────────────────────────────

def _parse_ax_tree(page: "Page") -> tuple[list[str], list[dict]]:
    """同步包装：解析无障碍树。"""
    return _run_async(_async_parse_ax_tree(page))


def _resolve_element(page: "Page", item: dict) -> Optional[object]:
    """同步包装：精确定位元素。"""
    return _run_async(_async_resolve_element(page, item))


def _refresh_item_map() -> str:
    """同步包装：刷新 UUID 映射。"""
    return _run_async(_async_refresh_item_map())


# ── 导出异步函数（供 browser.py 中的异步实现直接调用） ────────────────
__all__ = [
    '_parse_ax_tree',
    '_resolve_element',
    '_refresh_item_map',
    '_async_parse_ax_tree',
    '_async_resolve_element',
    '_async_refresh_item_map',
]
