"""
server/servers/system.py —— 系统工具处理器。

涵盖: finish / system_command / change_directory / ask_user / find_file / edit_file / get_cwd / set_cwd_explicit
"""

from __future__ import annotations

import os
import sys
import threading
import subprocess

from config import get_config, set_where
from logger import log
from server.router import ToolResult, ToolContext

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
        return f'目录已切换到: {full_path}'
    else:
        return f'目录不存在: {full_path}'


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
        return f'命令执行超时（超过 {timeout} 秒）: {command}'

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

    input_log = f'Shell Input: {command}'
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


def ask_user(args: dict, ctx: ToolContext) -> ToolResult:
    question = args.get('question', '')
    reply = ctx.input_func('>> ')
    text = f'用户回复: {reply}' if reply else '用户什么都没回复。'
    return ToolResult(
        text=text,
        log_msg=question,
        log_role='QUESTION',
    )