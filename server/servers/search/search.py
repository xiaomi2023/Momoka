"""
server/servers/search/search.py — Search tool handlers.

Covers: grep / glob
"""

from __future__ import annotations

import os
import re
import traceback
from pathlib import Path

from config import get_config
from logger import log
from server.types import ToolResult, ToolContext


# ── grep 工具处理器 ─────────────────────────────────────────────────────────

def grep(args: dict, ctx: ToolContext) -> ToolResult:
    """在文件中搜索文本模式（支持正则表达式）。"""
    pattern = args.get('pattern', '')
    search_path = args.get('path') or _get_cwd()
    file_glob = args.get('glob')
    case_sensitive = args.get('case_sensitive', False)
    max_results = args.get('max_results', 100)

    log_label = f'Grep: {pattern}'

    try:
        # 编译正则表达式
        flags = 0 if case_sensitive else re.IGNORECASE
        try:
            regex = re.compile(pattern, flags)
        except re.error as e:
            return ToolResult(
                text=f'<Invalid regex pattern: {pattern}\nError: {e}>',
                log_msg=log_label,
            )

        # 获取要搜索的文件列表
        files = _get_files(search_path, file_glob)

        if not files:
            return ToolResult(
                text=f'<No files found matching criteria in: {search_path}>',
                log_msg=log_label,
            )

        # 在所有文件中搜索
        results: list[str] = []
        files_searched = 0
        for file_path in files:
            if len(results) >= max_results:
                break
            try:
                matches = _search_file(file_path, regex)
                if matches:
                    for line_num, line_content in matches:
                        if len(results) >= max_results:
                            break
                        # 限制每行显示长度
                        if len(line_content) > 300:
                            line_content = line_content[:300] + '...'
                        results.append(f'{file_path}:{line_num}: {line_content}')
                    files_searched += 1
            except (UnicodeDecodeError, PermissionError, OSError):
                # 跳过无法读取的文件
                continue

        if not results:
            return ToolResult(
                text=f'<No matches found for pattern: {pattern}>',
                log_msg=log_label,
            )

        total_matches = len(results)
        output = f'Found {total_matches} matches for pattern "{pattern}":\n\n'
        output += '\n'.join(results)
        if total_matches >= max_results:
            output += f'\n\n... (limited to {max_results} results, use max_results parameter to see more)'

        return ToolResult(
            text=output,
            log_msg=f'{log_label} -> {total_matches} results' if total_matches > 1 else f'{log_label} -> {total_matches} result',
        )

    except Exception as e:
        log(f'grep error | {traceback.format_exc()}')
        return ToolResult(
            text=f'<Error executing grep: {type(e).__name__}: {e}>',
            log_msg=log_label,
        )


# ── glob 工具处理器 ─────────────────────────────────────────────────────────

def glob(args: dict, ctx: ToolContext) -> ToolResult:
    """根据文件名模式查找文件。"""
    pattern = args.get('pattern', '')
    search_path = args.get('path') or _get_cwd()

    log_label = f'Glob: {pattern}'

    try:
        # 使用 pathlib 的 glob 功能
        from pathlib import Path
        import fnmatch

        search_path = Path(search_path)
        if not search_path.exists():
            return ToolResult(
                text=f'<Path does not exist: {search_path}>',
                log_msg=log_label,
            )

        # 解析 glob 模式
        # 支持 ** 递归匹配
        if '**' in pattern:
            # 递归搜索
            files = list(search_path.rglob(pattern.replace('**/', '').replace(f'**{os.sep}', '')))
        else:
            # 仅当前目录
            files = list(search_path.glob(pattern))

        # 过滤出文件（不包括目录）
        files = [f for f in files if f.is_file()]

        if not files:
            return ToolResult(
                text=f'<No files found matching pattern: {pattern}>',
                log_msg=log_label,
            )

        # 格式化输出
        file_list = [str(f) for f in sorted(files)]
        total = len(file_list)
        output = f'Found {total} files matching "{pattern}":\n\n'
        output += '\n'.join(file_list)

        return ToolResult(
            text=output,
            log_msg=f'{log_label} -> {total} results' if total > 1 else f'{log_label} -> {total} result',
        )

    except Exception as e:
        log(f'glob error | {traceback.format_exc()}')
        return ToolResult(
            text=f'<Error executing glob: {type(e).__name__}: {e}>',
            log_msg=log_label,
        )


# ── 辅助函数 ─────────────────────────────────────────────────────────────────

def _get_cwd() -> str:
    """获取当前工作目录。"""
    cfg = get_config()
    return cfg.get('where') or cfg['work_dir']


# 默认排除的目录名称（不区分大小写）
IGNORED_DIRS: set[str] = {
    '.git', '.svn', '.hg',               # 版本控制
    'node_modules', '.npm',              # Node.js
    '__pycache__', '.pytest_cache',      # Python 缓存
    '.venv', 'venv', 'env',              # Python 虚拟环境
    '.idea', '.vscode',                  # IDE 配置
    '.mypy_cache', '.ruff_cache',        # Python 工具缓存
    'bower_components',                  # 前端包
    'vendor',                            # PHP/Go vendor
    '.next', '.nuxt',                    # 构建产物
    'target',                            # Rust/Java 构建产物
    'bin', 'obj',                        # .NET 构建产物
}

# 默认排除的文件扩展名（二进制/不可搜索格式）
IGNORED_EXTENSIONS: set[str] = {
    # 图片
    '.png', '.jpg', '.jpeg', '.gif', '.bmp', '.ico', '.svg', '.webp', '.tiff',
    # 字体
    '.ttf', '.otf', '.woff', '.woff2', '.eot',
    # 音视频
    '.mp3', '.mp4', '.wav', '.avi', '.mov', '.mkv', '.flv',
    # 压缩包
    '.zip', '.tar', '.gz', '.bz2', '.xz', '.7z', '.rar',
    # 二进制/可执行
    '.exe', '.dll', '.so', '.dylib', '.bin', '.obj', '.lib', '.pdb',
    '.class', '.jar', '.war', '.pyc', '.pyo', '.pyd',
    '.o', '.a', '.lo', '.la',
    # 数据库
    '.db', '.sqlite', '.sqlite3',
    # 文档二进制格式（应由专门工具查看）
    '.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx',
    # 其他
    '.iso', '.img', '.lock', '.map', '.min.js', '.min.css',
}


def _get_files(search_path: str, file_glob: str | None) -> list[str]:
    """获取要搜索的文件列表。"""
    search_path = Path(search_path)

    if search_path.is_file():
        return [str(search_path)]

    if not search_path.is_dir():
        return []

    files = []
    if file_glob:
        # 使用 glob 模式过滤
        if '**' in file_glob:
            files = [str(f) for f in search_path.rglob(file_glob.replace('**/', '').replace(f'**{os.sep}', ''))]
        else:
            files = [str(f) for f in search_path.glob(file_glob)]
    else:
        # 递归获取所有文件，但跳过被忽略的目录和二进制文件扩展名
        for f in search_path.rglob('*'):
            if not f.is_file():
                continue
            # 检查是否在忽略的目录中
            if _is_in_ignored_dir(f, search_path):
                continue
            # 检查是否是被忽略的扩展名
            if f.suffix.lower() in IGNORED_EXTENSIONS:
                continue
            files.append(str(f))

    return files


def _is_in_ignored_dir(file_path: Path, root: Path) -> bool:
    """检查文件是否位于被忽略的目录中。"""
    try:
        # 获取文件相对于根目录的路径部分
        rel = file_path.relative_to(root)
        # 检查路径的每个部分是否在忽略列表中
        for part in rel.parts:
            if part.lower() in IGNORED_DIRS:
                return True
    except ValueError:
        pass
    return False


def _search_file(file_path: str, regex: re.Pattern) -> list[tuple[int, str]]:
    """在单个文件中搜索正则表达式，返回 (行号, 内容) 列表。"""
    matches = []
    encoding = get_config().get('encoding', 'utf-8')

    with open(file_path, 'r', encoding=encoding, errors='ignore') as f:
        for line_num, line in enumerate(f, 1):
            if regex.search(line):
                matches.append((line_num, line.rstrip()))

    return matches
