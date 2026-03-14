import subprocess
import os
import sys
from config import get_config, set_where
from logger import log

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


# 用于分隔命令输出与工作目录的唯一标记
# 注意：不能含有 CMD 特殊字符（< > | & 等），否则会被 shell 解释
_CWD_SEPARATOR = '==CWD_MARKER=='


def set_cwd_explicit(path: str) -> str:
    """供 CD 指令显式切换工作目录。"""
    import os
    full_path = path if os.path.isabs(path) else os.path.join(_get_cwd(), path)
    if os.path.isdir(full_path):
        _set_cwd(full_path)
        return f'目录已切换到: {full_path}'
    else:
        return f'目录不存在: {full_path}'


def system_command(command: str, inputs: str | list[str] | None = None) -> str:
    import threading
    import subprocess

    cwd = _get_cwd()
    log(f'system_command | cwd: {cwd} | command: {command} | inputs: {inputs}')

    # 预处理输入内容
    input_data = None
    if inputs is not None:
        if isinstance(inputs, list):
            # 将列表合并为换行分隔的字符串，确保最后有一个换行
            input_data = "\n".join(map(str, inputs)) + "\n"
        else:
            input_data = str(inputs)
            if not input_data.endswith('\n'):
                input_data += '\n'

        # 转换为字节流
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
        # start_new_session 在 Windows 上不受支持，改用 CREATE_NEW_PROCESS_GROUP
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

    # 读取线程逻辑保持不变
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
            # 发送输入并等待
            proc.stdin.write(input_data)
            proc.stdin.close()  # 必须关闭，否则子进程可能一直等待输入

        proc.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        timed_out = True
        # 跨平台终止进程树
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

    # 确保关闭所有管道
    if proc.stdout: proc.stdout.close()
    if proc.stderr: proc.stderr.close()

    if timed_out:
        return f'命令执行超时（超过 {timeout} 秒）: {command}'

    encoding = get_config()['encoding']
    stdout_str = b''.join(stdout_chunks).decode(encoding, errors='replace').rstrip('\r\n')
    stderr_str = b''.join(stderr_chunks).decode(encoding, errors='replace').rstrip('\r\n')

    output = stdout_str
    if stderr_str:
        output += f'\n[STDERR]: {stderr_str}'

    return output or '（输出为空）'

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