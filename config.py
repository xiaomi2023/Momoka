import json

CONFIG_FILE = 'config.json'
WORKING_CONFIG_FILE = 'working_config.json'


# ── 静态配置（config.json）────────────────────────────────────────────────────

def get_config() -> dict:
    """读取静态配置与运行时配置，合并后返回统一字典。

    静态字段（config.json）：api_key, work_dir, base_url, model, encoding, summary, dialogue
    运行时字段（working_config.json）：edit_mode, file_name, where
    """
    with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
        config = json.load(f)
    working = _get_working_config()
    # 运行时字段覆盖静态字段（如有同名）
    config.update(working)
    # 向后兼容：where 为空时回退到 work_dir
    if not config.get('where'):
        config['where'] = config['work_dir']
    return config


# ── 运行时配置（working_config.json）─────────────────────────────────────────

def _get_working_config() -> dict:
    """读取运行时配置文件，返回字典。"""
    with open(WORKING_CONFIG_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)


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


# ── 模块加载时初始化运行时状态 ────────────────────────────────────────────────
# 将 where 重置为 work_dir，确保每次启动从工作目录开始
_static = json.load(open(CONFIG_FILE, encoding='utf-8'))
_update_working_config(
    where=_static['work_dir'],
)