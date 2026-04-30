"""
server/servers/memory/memory.py —— memorize / recall 处理器。

维护一个 JSONL 文件用于持久化存储记忆。
每条记录包含：content（记忆内容）、keywords（关键词列表）、timestamp（时间戳）。
"""

from __future__ import annotations

import json
import os
import time

from config import get_config as _get_config
from server.types import ToolResult, ToolContext

# 记忆文件路径：存放在 memory server 目录下的 memory_data.jsonl
_MEMORY_DIR = os.path.dirname(os.path.abspath(__file__))
_MEMORY_FILENAME = 'memory_data.jsonl'


def _get_memory_filepath() -> str:
    """获取记忆文件的完整路径。"""
    return os.path.join(_MEMORY_DIR, _MEMORY_FILENAME)


def _append_memory(content: str, keywords: list[str]) -> None:
    """追加一条记忆到 JSONL 文件。"""
    filepath = _get_memory_filepath()
    record = {
        'content': content,
        'keywords': keywords,
        'timestamp': time.time(),
    }
    with open(filepath, 'a', encoding='utf-8') as f:
        f.write(json.dumps(record, ensure_ascii=False) + '\n')


def _search_memories(query: str, max_results: int = 20) -> list[dict]:
    """在记忆文件中搜索匹配的记忆。

    匹配规则（不区分大小写）：
    - 关键词列表中的任意词包含 query 子串
    - 记忆内容包含 query 子串

    Args:
        query: 搜索关键词
        max_results: 最大返回条数

    Returns:
        匹配的记忆记录列表（按时间倒序）
    """
    filepath = _get_memory_filepath()
    if not os.path.exists(filepath):
        return []

    query_lower = query.lower()
    matched: list[dict] = []

    with open(filepath, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue

            # 检查 content 是否匹配
            content = record.get('content', '')
            if query_lower in content.lower():
                matched.append(record)
                continue

            # 检查 keywords 是否匹配
            keywords = record.get('keywords', [])
            for kw in keywords:
                if query_lower in kw.lower():
                    matched.append(record)
                    break

    # 按时间倒序排列（最新的在前）
    matched.sort(key=lambda r: r.get('timestamp', 0), reverse=True)
    return matched[:max_results]


def _format_timestamp(ts: float) -> str:
    """将时间戳格式化为可读字符串。"""
    return time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(ts))


# ── Tool Handlers ─────────────────────────────────────────────────────────

def memorize(args: dict, ctx: ToolContext) -> ToolResult:
    """memorize 工具处理器：将信息存入长期记忆。"""
    content = args.get('content', '')
    keywords = args.get('keywords', [])

    if not content:
        return ToolResult(
            text='<Error: Content cannot be empty>',
            log_msg='Memorize failed',
            log_role='TOOL',
        )

    if not isinstance(keywords, list):
        keywords = [str(keywords)]

    _append_memory(content, keywords)

    kw_str = ', '.join(keywords) if keywords else '(no keywords)'
    msg = f'Memorize: {content[:50]}{"..." if len(content) > 50 else ""} ({kw_str})'

    return ToolResult(
        text=f'<Memorize: {content}>',
        log_msg=msg,
        log_role='MEMORY',
    )


def _merge_memories(*memory_lists: list[dict]) -> list[dict]:
    """合并多个记忆列表，按 content 去重，按时间倒序排列。"""
    seen: set[str] = set()
    merged: list[dict] = []
    for mem_list in memory_lists:
        for mem in mem_list:
            content = mem.get('content', '')
            if content not in seen:
                seen.add(content)
                merged.append(mem)
    merged.sort(key=lambda r: r.get('timestamp', 0), reverse=True)
    return merged


def recall(args: dict, ctx: ToolContext) -> ToolResult:
    """recall 工具处理器：搜索长期记忆。

    支持单个 query 字符串，或 query 字符串列表（每个元素分别查询后合并去重）。
    """
    query_raw = args.get('query', '')

    # 统一转为列表：单个字符串 → [字符串]，列表 → 原样
    if isinstance(query_raw, str):
        queries = [query_raw] if query_raw else []
    elif isinstance(query_raw, list):
        queries = [q for q in query_raw if isinstance(q, str) and q.strip()]
    else:
        queries = []

    if not queries:
        return ToolResult(
            text='<Error: Search keywords cannot be empty>',
            log_msg='Recall failed',
            log_role='TOOL',
        )

    if len(queries) == 1:
        # 单个查询，行为不变
        memories = _search_memories(queries[0])
        query_display = queries[0]
    else:
        # 多个查询，分别搜索后合并去重
        all_results = [_search_memories(q) for q in queries]
        memories = _merge_memories(*all_results)
        query_display = ', '.join(queries)

    if not memories:
        return ToolResult(
            text=f'<No memory was found related to "{query_display}">',
            log_msg=f'Recall failed',
            log_role='MEMORY',
        )

    # 格式化结果
    if len(queries) > 1:
        lines = [f'Find {len(memories)} related memories (searched: {query_display}):', '']
    else:
        lines = [f'Find {len(memories)} related memories:', '']

    for i, mem in enumerate(memories, 1):
        content = mem.get('content', '')
        ts = _format_timestamp(mem.get('timestamp', 0))
        lines.append(f'{i}. [{ts}] {content}')
        lines.append('')

    result_text = '\n'.join(lines)

    return ToolResult(
        text=result_text,
        log_msg=f'Recall: [{query_display}]',
        log_role='MEMORY',
    )
