/**
 * 在页面中搜索包含指定文字的可见元素
 * 用于 browser_find 功能
 * 
 * @param {string} needle - 要搜索的文字
 * @param {number} limit - 最大返回结果数
 * @returns {Array<{tag: string, selector: string, snippet: string}>} 匹配的元素信息
 */
([needle, limit]) => {
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
            sel += '.' + el.className.trim().split(/\s+/).join('.');
        const snippet = node.textContent.trim().slice(0, 80);
        matches.push({ tag: el.tagName.toLowerCase(), selector: sel, snippet });
    }
    return matches;
}
