/**
 * 提取页面正文内容并转换为 Markdown 格式
 * 用于 browser_read 功能的 text 模式
 */
() => {
    const lines = [];
    const processed = new WeakSet();
    const walker = document.createTreeWalker(
        document.body, NodeFilter.SHOW_TEXT, null
    );
    let node;

    // 辅助：获取元素的标签路径
    function getTagPath(el) {
        const tags = [];
        let curr = el;
        while (curr && curr !== document.body) {
            if (curr.tagName) tags.unshift(curr.tagName.toLowerCase());
            curr = curr.parentElement;
        }
        return tags;
    }

    // 辅助：检查元素是否在代码块内
    function isInCodeBlock(el) {
        let curr = el;
        while (curr && curr !== document.body) {
            const tag = curr.tagName.toLowerCase();
            if (tag === 'pre' || tag === 'code') return true;
            if (curr.classList && curr.classList.contains('code-block')) return true;
            curr = curr.parentElement;
        }
        return false;
    }

    // 辅助：检查元素是否在表格内
    function getTableContext(el) {
        let curr = el;
        while (curr && curr !== document.body) {
            if (curr.tagName.toLowerCase() === 'table') return curr;
            curr = curr.parentElement;
        }
        return null;
    }

    // 辅助：检查是否在 blockquote 内
    function isInBlockquote(el) {
        let curr = el;
        while (curr && curr !== document.body) {
            if (curr.tagName.toLowerCase() === 'blockquote') return true;
            curr = curr.parentElement;
        }
        return false;
    }

    // 辅助：检查是否在列表项内
    function getListContext(el) {
        let curr = el;
        while (curr && curr !== document.body) {
            const tag = curr.tagName.toLowerCase();
            if (tag === 'ul' || tag === 'ol' || tag === 'li') {
                return { tag, parent: curr.parentElement };
            }
            curr = curr.parentElement;
        }
        return null;
    }

    // 辅助：获取链接的 href
    function getLinkHref(el) {
        let curr = el;
        while (curr && curr !== document.body) {
            if (curr.tagName.toLowerCase() === 'a') {
                return curr.getAttribute('href') || '';
            }
            curr = curr.parentElement;
        }
        return '';
    }

    // 表格解析：收集所有表格数据
    const tableData = new Map(); // table element -> { rows: [[{text, isHeader}]] }
    document.querySelectorAll('table').forEach(table => {
        const rows = [];
        table.querySelectorAll('tr').forEach(tr => {
            const cells = [];
            tr.querySelectorAll('th, td').forEach(cell => {
                cells.push({
                    text: cell.textContent.trim(),
                    isHeader: cell.tagName.toLowerCase() === 'th'
                });
            });
            if (cells.length > 0) rows.push(cells);
        });
        tableData.set(table, rows);
    });

    // 已处理的表格集合
    const processedTables = new Set();

    while ((node = walker.nextNode())) {
        const t = node.textContent.trim();
        if (!t) continue;
        const el = node.parentElement;
        if (!el) continue;
        const tag = el.tagName.toLowerCase();

        // 跳过脚本/样式
        if (['script','style','noscript'].includes(tag)) continue;
        // 过滤隐藏元素
        if (el.offsetParent === null && tag !== 'body') continue;
        // 如果祖先元素已被处理，跳过
        if (processed.has(el)) continue;

        // ── 标题 ─────────────────────────────────────────────
        if (/^h[1-6]$/.test(tag)) {
            const level = parseInt(tag[1]);
            lines.push('#'.repeat(level) + ' ' + t);
            el.querySelectorAll('*').forEach(c => processed.add(c));
            processed.add(el);
            continue;
        }

        // ── 表格 ─────────────────────────────────────────────
        const tableContext = getTableContext(el);
        if (tableContext && !processedTables.has(tableContext)) {
            const rows = tableData.get(tableContext);
            if (rows && rows.length > 0) {
                // 生成 Markdown 表格
                const maxCells = Math.max(...rows.map(r => r.length));
                const headerRow = rows[0];
                const isHeader = rows.length > 0 && headerRow.some(c => c.isHeader);

                // 表头
                if (isHeader) {
                    const header = headerRow.map(c => c.text || ' ').join(' | ');
                    lines.push('| ' + header + ' |');
                    lines.push('| ' + Array(maxCells).fill('---').join(' | ') + ' |');
                    // 数据行
                    for (let i = 1; i < rows.length; i++) {
                        const cells = rows[i].map(c => c.text || ' ').join(' | ');
                        lines.push('| ' + cells + ' |');
                    }
                } else {
                    // 无表头，首行作为表头
                    const header = rows[0].map(c => c.text || ' ').join(' | ');
                    lines.push('| ' + header + ' |');
                    lines.push('| ' + Array(maxCells).fill('---').join(' | ') + ' |');
                    for (let i = 1; i < rows.length; i++) {
                        const cells = rows[i].map(c => c.text || ' ').join(' | ');
                        lines.push('| ' + cells + ' |');
                    }
                }
                processedTables.add(tableContext);
                tableContext.querySelectorAll('*').forEach(c => processed.add(c));
                processed.add(tableContext);
            }
            continue;
        }

        // 跳过已处理表格内的单元格
        if (tableContext && processedTables.has(tableContext)) {
            continue;
        }

        // ── 引用块 ────────────────────────────────────────────
        if (isInBlockquote(el) && tag === 'p') {
            lines.push('> ' + t);
            continue;
        }

        // ── 代码块 ────────────────────────────────────────────
        if (tag === 'pre' || tag === 'code') {
            const parentTag = el.parentElement?.tagName.toLowerCase();
            if (tag === 'code' && parentTag !== 'pre') {
                // 行内代码
                lines.push('`' + t + '`');
            } else if (tag === 'pre' || parentTag === 'pre') {
                // 代码块
                const codeEl = tag === 'pre' ? el.querySelector('code') : el;
                const code = codeEl ? codeEl.textContent.trim() : t;
                // 检测语言
                const langClass = codeEl?.className || '';
                const langMatch = langClass.match(/language-(\w+)/);
                const lang = langMatch ? langMatch[1] : '';
                lines.push('```' + lang);
                lines.push(code);
                lines.push('```');
                if (tag === 'pre') {
                    el.querySelectorAll('*').forEach(c => processed.add(c));
                    processed.add(el);
                }
            }
            continue;
        }

        // ── 列表 ──────────────────────────────────────────────
        const listContext = getListContext(el);
        if (listContext && tag === 'li') {
            const prefix = listContext.tag === 'ol'
                ? (() => {
                    const siblings = Array.from(listContext.parent.querySelectorAll(':scope > li'));
                    const idx = siblings.indexOf(el) + 1;
                    return idx + '.';
                  })()
                : '-';
            lines.push(prefix + ' ' + t);
            continue;
        }

        // ── 链接 ──────────────────────────────────────────────
        if (tag === 'a') {
            lines.push(t);
            continue;
        }

        // ── 粗体/斜体 ─────────────────────────────────────────
        if (tag === 'strong' || tag === 'b') {
            lines.push('**' + t + '**');
            continue;
        }
        if (tag === 'em' || tag === 'i') {
            lines.push('*' + t + '*');
            continue;
        }

        // ── 默认：普通文本 ────────────────────────────────────
        lines.push(t);
    }
    return lines;
}
