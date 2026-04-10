import json
import os

_HERE = os.path.dirname(os.path.abspath(__file__))

# 优先使用 debug 配置，不存在则回退到默认配置
_config_debug = os.path.join(_HERE, 'config_debug.json')
_config_default = os.path.join(_HERE, 'config.json')
CONFIG_FILE = _config_debug if os.path.exists(_config_debug) else _config_default

_working_config_debug = os.path.join(_HERE, 'working_config_debug.json')
_working_config_default = os.path.join(_HERE, 'working_config.json')
WORKING_CONFIG_FILE = _working_config_debug if os.path.exists(_working_config_debug) else _working_config_default


# ── 静态配置（config.json）────────────────────────────────────────────────────

def get_config() -> dict:
    """读取静态配置与运行时配置，合并后返回统一字典。"""
    with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
        config = json.load(f)
    working = _get_working_config()
    # 运行时字段覆盖静态字段（如有同名）
    config.update(working)
    # work_dir 不存在时使用程序当前目录保底
    if not config.get('work_dir') or not os.path.exists(config['work_dir']):
        config['work_dir'] = _HERE
    # 向后兼容：where 为空时回退到 work_dir
    if not config.get('where'):
        config['where'] = config['work_dir']
    return config


# ── 运行时配置（working_config.json）─────────────────────────────────────────

def _get_working_config() -> dict:
    """读取运行时配置文件，返回字典。"""
    with open(WORKING_CONFIG_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)


def get_working_config() -> dict:
    """公开接口：读取运行时配置文件，返回字典。"""
    return _get_working_config()


def _save_working_config(working: dict):
    """将运行时配置字典写回 working_config.json。"""
    with open(WORKING_CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(working, f, ensure_ascii=False, indent=2)


def _update_working_config(**kwargs):
    """通用运行时配置更新：读取 → 修改指定字段 → 写回。"""
    working = _get_working_config()
    working.update(kwargs)
    _save_working_config(working)


def set_where(path: str):
    """更新当前工作目录到运行时配置。"""
    _update_working_config(where=path)


def set_wait(seconds: int):
    """更新通用超时时长到运行时配置。"""
    _update_working_config(wait=seconds)


def set_wait_download(seconds: int):
    """更新浏览器下载专用超时时长到运行时配置。"""
    _update_working_config(wait_download=seconds)


def set_read_limits(max_lines: int | None = None, max_size_kb: int | None = None):
    """更新文件阅读限制到运行时配置。

    Args:
        max_lines:    最大行数上限，不超过 50000 行。
        max_size_kb:  最大体积上限（KB），不超过 5120 KB（5 MB）。
    """
    updates = {}
    if max_lines is not None:
        updates['read_max_lines'] = min(max_lines, 50000)
    if max_size_kb is not None:
        updates['read_max_size_kb'] = min(max_size_kb, 5120)
    if updates:
        _update_working_config(**updates)


# ── 模块加载时初始化运行时状态 ────────────────────────────────────────────────
# 注意：此函数应在程序入口（main.py）显式调用，而非导入时自动执行
# 将 where 重置为 work_dir，确保每次启动从工作目录开始

def initialize_working_config():
    """初始化运行时配置，确保每次启动从默认工作目录开始。
    
    应在程序入口（main.py）启动时显式调用一次。
    """
    with open(CONFIG_FILE, encoding='utf-8') as f:
        _static = json.load(f)
    _update_working_config(
        where=_static['work_dir'],
        wait=10,
        wait_download=60,
        read_max_lines=1000,
        read_max_size_kb=100,
    )