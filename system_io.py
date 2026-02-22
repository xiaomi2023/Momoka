import subprocess
import os
from config import get_config, set_where
from logger import log

COMMAND_TIMEOUT = 10  # 终端命令超时秒数

# 持久化的环境状态（进程内跨调用保持）
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
        return f'目录已切换到：{full_path}'
    else:
        return f'目录不存在：{full_path}'


def system_command(command: str) -> str:
    cwd = _get_cwd()
    log(f'system_command | cwd: {cwd} | command: {command}')

    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            encoding=get_config()['encoding'],
            errors='replace',
            cwd=cwd,
            env=_env,
            timeout=COMMAND_TIMEOUT,
        )
    except subprocess.TimeoutExpired:
        msg = f'命令执行超时（超过 {COMMAND_TIMEOUT} 秒）：{command}'
        log(f'system_command timeout: {command}')
        return msg
    except Exception as e:
        log(f'system_command error: {e}')
        return str(e)

    output = result.stdout.rstrip('\r\n')
    if result.stderr:
        output += f'\n[STDERR]: {result.stderr.rstrip()}'

    log(f'system_command | output: {output}')
    return output or '（输出为空）'

def get_cwd() -> str:
    """返回当前持久化工作目录。"""
    return _get_cwd()