"""
server/servers/system/system.py —— 系统工具处理器。

涵盖: finish / system_command / change_directory / find_file / edit_file / get_cwd / set_cwd_explicit
         read_file / replace_file / read_sheet
"""

from __future__ import annotations

import os
import sys
import threading
import subprocess
import traceback

from config import get_config, set_where
from logger import log
from server import ToolResult, ToolContext
from server.servers.system.office import read_docx, read_sheet_tool

_IS_WINDOWS = sys.platform == 'win32'

# ── 持久化的环境状态（进程内跨调用保持）────────────────────────────────────
_env = os.environ.copy()
_cwd: str | None = None  # 延迟初始化，首次调用时从 config 读取


def _get_cwd() -> str:
    global _cwd
    if _cwd is None:
        cfg = get_config()
        _cwd = cfg.get('where') or cfg['work_dir']
    return _cwd


def _set_cwd(path: str):
    global _cwd
    _cwd = path
    set_where(path)


_CWD_SEPARATOR = '==CWD_MARKER=='


def set_cwd_explicit(path: str) -> str:
    """供 change_directory 工具显式切换工作目录。"""
    full_path = path if os.path.isabs(path) else os.path.join(_get_cwd(), path)
    if os.path.isdir(full_path):
        _set_cwd(full_path)
        return f'<Directory has been changed to: {full_path}>'
    else:
        return f'<Directory does not exist: {full_path}>'


def _system_command_impl(command: str, inputs: str | list[str] | None = None) -> str:
    cwd = _get_cwd()
    log(f'system_command | cwd: {cwd} | command: {command} | inputs: {inputs}')

    input_data = None
    if inputs is not None:
        if isinstance(inputs, list):
            input_data = "\n".join(map(str, inputs)) + "\n"
        else:
            input_data = str(inputs)
            if not input_data.endswith('\n'):
                input_data += '\n'

        encoding = get_config()['encoding']
        input_data = input_data.encode(encoding)

    try:
        kwargs = dict(
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            stdin=subprocess.PIPE if input_data else subprocess.DEVNULL,
            cwd=cwd,
            env=_env,
        )
        if _IS_WINDOWS:
            kwargs['creationflags'] = subprocess.CREATE_NEW_PROCESS_GROUP
        else:
            kwargs['start_new_session'] = True

        proc = subprocess.Popen(command, **kwargs)
    except Exception as e:
        log(f'system_command error: {e}')
        return str(e)

    stdout_chunks: list[bytes] = []
    stderr_chunks: list[bytes] = []

    def _read(pipe, chunks):
        try:
            for chunk in iter(lambda: pipe.read(4096), b''):
                chunks.append(chunk)
        except Exception:
            pass

    t_out = threading.Thread(target=_read, args=(proc.stdout, stdout_chunks), daemon=True)
    t_err = threading.Thread(target=_read, args=(proc.stderr, stderr_chunks), daemon=True)
    t_out.start()
    t_err.start()

    timed_out = False
    timeout = get_config().get('wait', 10)

    try:
        if input_data:
            proc.stdin.write(input_data)
            proc.stdin.close()

        proc.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        timed_out = True
        if _IS_WINDOWS:
            subprocess.run(
                f'taskkill /F /T /PID {proc.pid}',
                shell=True, capture_output=True
            )
        else:
            import signal
            try:
                os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
            except ProcessLookupError:
                proc.kill()

    t_out.join(timeout=1)
    t_err.join(timeout=1)

    if proc.stdout: proc.stdout.close()
    if proc.stderr: proc.stderr.close()

    if timed_out:
        return f'<Command execution timed out: {command}>'

    cfg = get_config()
    encoding = cfg['encoding']
    max_lines: int = cfg.get('max_lines', 200)

    stdout_str = b''.join(stdout_chunks).decode(encoding, errors='replace').rstrip('\r\n')
    stderr_str = b''.join(stderr_chunks).decode(encoding, errors='replace').rstrip('\r\n')

    def _truncate(text: str) -> str:
        if not text:
            return text
        lines = text.splitlines()
        if len(lines) > max_lines:
            omitted = len(lines) - max_lines
            truncated = lines[:max_lines]
            truncated.append(f'... （已省略 {omitted} 行，共 {len(lines)} 行）')
            return '\n'.join(truncated)
        return '\n'.join(lines)

    output = _truncate(stdout_str)
    if stderr_str:
        output += f'\n[STDERR]: {_truncate(stderr_str)}'

    return output or '(EMPTY OUTPUT)'


def get_cwd() -> str:
    """返回当前持久化工作目录。"""
    return _get_cwd()


# ── 文件读写 ──────────────────────────────────────────────────────────────

def find_file(filename: str, encoding: str = 'utf-8') -> str:
    """读取文件内容，失败时直接抛出异常。"""
    with open(filename, 'r', encoding=encoding) as f:
        return f.read()


def edit_file(filename: str, text: str, encoding: str = 'utf-8'):
    """将 text 覆盖写入指定文件。"""
    with open(filename, 'w', encoding=encoding) as f:
        f.write(text)


# ── 工具处理器函数 ─────────────────────────────────────────────────────────

def finish(args: dict, ctx: ToolContext) -> ToolResult:
    return ToolResult(text='FINISH', is_finish=True)


def system_command(args: dict, ctx: ToolContext) -> ToolResult:
    command = args.get('command', '')
    inputs = args.get('inputs')

    input_log = f'\nShell Input: {command}'
    if inputs is not None:
        input_log += f' | input={str(inputs).split()}'
    input_log += '\n'

    output = _system_command_impl(command, inputs=inputs)
    output_log = f'Shell Output: {"(NULL)" if output == "" else chr(10) + output}'

    return ToolResult(
        text=output or '(EMPTY OUTPUT)',
        log_msg=[(input_log, 'SHELL'), (output_log, 'SHELL')],
    )


def change_directory(args: dict, ctx: ToolContext) -> ToolResult:
    path = args.get('path', '')
    result = set_cwd_explicit(path)
    return ToolResult(
        text=result,
        log_msg=f'Switch Directory: {path}',
    )



# ── edit_file tool handler ────────────────────────────────────────────────

def edit_file_tool(args: dict, ctx: ToolContext) -> ToolResult:
    """edit_file 工具处理器（覆盖写入文件）。"""
    file_path = args.get('file_path', '')
    content = args.get('content', '')
    encoding = args.get('encoding') or ctx.cfg.get('encoding', 'utf-8')
    try:
        edit_file(file_path, content, encoding)
        write_lines = len(content.splitlines())
        return ToolResult(
            text=f'<Written File: {file_path}>',
            log_msg=f'Write File: {file_path} (+{write_lines})',
        )
    except Exception as e:
        log(f'edit_file error | {file_path}\n{traceback.format_exc()}')
        return ToolResult(
            text=f'<The following error occurred while editing the file: \n{type(e).__name__}: {e}\nConsider using the absolute path of the file>'
        )


# ── replace_file ──────────────────────────────────────────────────────────

def replace_file(args: dict, ctx: ToolContext) -> ToolResult:
    file_path = args.get('file_path', '')
    old_text = args.get('old_text', '')
    new_text = args.get('new_text', '')
    encoding = args.get('encoding') or ctx.cfg.get('encoding', 'utf-8')
    try:
        content = find_file(file_path, encoding)
        if old_text not in content:
            return ToolResult(text=f'<Replacement failed: The specified old text was not found in {file_path}>')
        new_content = content.replace(old_text, new_text, 1)
        edit_file(file_path, new_content, encoding)
        old_lines = len(old_text.splitlines())
        new_lines = len(new_text.splitlines())
        return ToolResult(
            text=f'<Replaced File: {file_path}>',
            log_msg=f'Edit File: {file_path} (-{old_lines},+{new_lines})',
        )
    except Exception as e:
        log(f'replace_file error | {file_path}\n{traceback.format_exc()}')
        return ToolResult(
            text=f'<The following error occurred while editing the file: \n{type(e).__name__}: {e}\n'
                 f'Consider using the absolute path of the file>'
        )


# ── read_file ─────────────────────────────────────────────────────────────

def read_file(args: dict, ctx: ToolContext) -> ToolResult:
    file_path = args.get('file_path', '')
    encoding = args.get('encoding') or ctx.cfg.get('encoding', 'utf-8')
    mode = args.get('mode', '')
    max_size_kb = ctx.cfg.get('read_max_size_kb', 100)
    max_lines = ctx.cfg.get('read_max_lines', 1000)

    log_label = f'Read File: {file_path}' + (' [doc]' if mode == 'doc' else '')

    try:
        max_size_bytes = max_size_kb * 1024
        file_size = os.path.getsize(file_path)
        if file_size > max_size_bytes:
            kb = file_size / 1024
            return ToolResult(
                text=(f'<File too large: {file_path} ({kb:.1f} KB, current size limit: {max_size_kb} KB), '
                      f'Consider using set_read_limits to increase the limits, '
                      f'or use other methods to read the content>'),
                log_msg=log_label,
            )

        # ── doc 模式 ─────────────────────────────────────────────────────
        if mode == 'doc':
            return _read_file_doc(file_path, encoding, max_lines, log_label, ctx)

        # ── 普通模式 ──────────────────────────────────────────────────────
        content = find_file(file_path, encoding)
        line_count = len(content.splitlines())
        if line_count > max_lines:
            return ToolResult(
                text=(f'<File too large: {file_path}({line_count} lines, current line limit: {max_lines}), '
                      f'Consider using set_read_limits to increase the limits, '
                      f'or use other methods to read the content>'),
                log_msg=log_label,
            )
        return ToolResult(
            text=f'Opened File: {file_path}\n{file_path}:\n{content}',
            file_contents={file_path: content},
            log_msg=log_label,
        )

    except Exception as e:
        log(f'read_file error | {file_path}\n{traceback.format_exc()}')
        return ToolResult(
            text=f'<The following error occurred while reading the file: \n{type(e).__name__}: {e}\n'
                 f'Consider using the absolute path of the file>',
            log_msg=log_label,
        )


def _read_file_doc(file_path: str, encoding: str, max_lines: int,
                   log_label: str, ctx: ToolContext) -> ToolResult:
    """read_file 的 doc 模式:调用 office 模块提取 Word 文档。"""
    return read_docx(file_path, encoding, max_lines, log_label)


# ── read_sheet ────────────────────────────────────────────────────────────

def read_sheet(args: dict, ctx: ToolContext) -> ToolResult:
    file_path = args.get('file_path', '')
    sheet_name = args.get('sheet_name', '').strip()
    sheet_mode = args.get('sheet_mode', 'all')
    range_str = args.get('range', '').strip()
    encoding = args.get('encoding') or ctx.cfg.get('encoding', 'utf-8')
    max_lines = ctx.cfg.get('read_max_lines', 1000)

    log_label = f'Read Sheet: {file_path}' + (f' [{sheet_name}]' if sheet_name else '')

    try:
        return read_sheet_tool(file_path, sheet_name, sheet_mode, range_str, encoding, max_lines, log_label)
    except Exception as e:
        log(f'read_sheet error | {file_path}\n{traceback.format_exc()}')
        return ToolResult(
            text=f'<The following error occurred while reading the table: \n{type(e).__name__}: {e}\n'
                 f'Consider using the absolute path of the file>',
            log_msg=log_label,
        )
