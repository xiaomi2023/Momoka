"""
server/servers/browser/accessibility.py —— 无障碍树解析与元素定位。

包含：
- 无障碍树解析（_parse_ax_tree）
- 元素精确定位（_resolve_element）
- 元素映射刷新（_refresh_item_map）
"""

from __future__ import annotations

import time
from typing import Optional

from rebrowser_playwright.sync_api import Page

from logger import log
from server.servers.browser.util import (
    _load_js,
    _safe_evaluate,
    _make_uid,
    _INTERACTIVE_ROLES,
    _timeout_ms,
)
from server.servers.browser.browser_state import (
    get_page,
    get_item_map,
    set_item_map,
    _maybe_switch_to_new_tab,
)


def _parse_ax_tree(page: "Page") -> tuple[list[str], list[dict]]:
    """用 locator 查询页面，返回 (text_lines, interactive_items)。

    text_lines:        页面正文文字行列表（过滤空行，支持 Markdown 格式）
    interactive_items: list of {uuid, role, name, locator_index, ...}
        - uuid:           8 位唯一 ID
        - role:           小写 role 字符串
        - name:           可访问名称（已保证非空）
        - locator_index:  该 role+name 组合下的第几个元素（0-based，用于精确定位）
        - href:           链接的绝对 URL（仅 link 角色）
        - action:         按钮的表单动作（仅 button 角色）
        - field_label:    输入框的标签文字（仅 input 类角色）
    """
    text_lines: list[str] = []
    interactive_items: list[dict] = []

    # ── 正文：通过 JS 遍历可见文字节点，增强 Markdown 转换 ────────────────
    _js_text = _load_js('extract_text.js')
    try:
        raw_text = _safe_evaluate(page, _js_text)
        text_lines = [t for t in (raw_text or []) if t.strip()]
    except Exception as e:
        log(f"browser | text extraction error: {e}")

    # ── 可交互元素：按 role 逐一查询，跳过链接（链接已在 MD 文本中显示 URL）───
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
                        name = locator_name  # name 恢复为正常显示名称
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

                try:
                    disabled = el.is_disabled()
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
                        action = (el.get_attribute('aria-pressed') or
                                 el.get_attribute('aria-expanded') or '')
                        if action:
                            extra_attrs['state'] = action
                    except Exception:
                        pass

                # 输入框：提取字段标签和当前填充值
                elif role in {'textbox', 'searchbox', 'combobox', 'spinbutton'}:
                    try:
                        # 尝试获取关联的 label
                        field_id = (el.get_attribute('id') or '').strip()
                        if field_id:
                            try:
                                label_el = page.locator(f'label[for="{field_id}"]')
                                if label_el.count() > 0:
                                    extra_attrs['field_label'] = (label_el.inner_text(timeout=500) or '').strip()
                            except Exception:
                                pass
                        # 获取当前填充值
                        current_val = (el.input_value(timeout=500) or '').strip()
                        if current_val:
                            extra_attrs['fill'] = current_val
                        # 获取输入类型
                        input_type = (el.get_attribute('type') or 'text').strip()
                        if input_type != 'text':
                            extra_attrs['input_type'] = input_type
                    except Exception:
                        pass

                # 复选框/单选框：提取选中状态
                elif role in {'checkbox', 'radio'}:
                    try:
                        checked = (el.get_attribute('aria-checked') or
                                 el.is_checked() if hasattr(el, 'is_checked') else False)
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


def _refresh_item_map() -> str:
    """等待页面稳定后重建 UUID 映射，返回新增/消失的元素 diff。"""
    _maybe_switch_to_new_tab()
    page = get_page()
    if page is None:
        return "<Page is not available>"

    try:
        page.wait_for_load_state("domcontentloaded", timeout=_timeout_ms())
    except Exception:
        pass
    try:
        page.wait_for_load_state("networkidle", timeout=3000)
    except Exception:
        pass
    time.sleep(0.3)

    old_map = get_item_map()
    _, interactive_items = _parse_ax_tree(page)
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
