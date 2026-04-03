"""
server/servers/browser_tooldef.py —— 浏览器工具定义。

涵盖: 所有 browse_* 工具

工具分为两组：
  - BROWSER_BASE_TOOLS: 浏览器基础工具（始终可用）
  - BROWSER_PAGE_TOOLS: 浏览器页面操作工具（仅在浏览器打开后可用）
"""

from __future__ import annotations

from config import get_config

# ── 浏览器基础工具（始终可用）────────────────────────────────────────────────

BROWSER_BASE_TOOLS: list[dict] = [
    {
        'type': 'function',
        'function': {
            'name': 'browse_open',
            'description': '用 Chromium 浏览器打开指定网页。',
            'parameters': {
                'type': 'object',
                'properties': {
                    'url': {'type': 'string', 'description': '要打开的网页 URL'},
                },
                'required': ['url'],
            },
        },
    },
    {
        'type': 'function',
        'function': {
            'name': 'browse_search',
            'description': '使用搜索引擎搜索关键词。',
            'parameters': {
                'type': 'object',
                'properties': {
                    'query': {'type': 'string', 'description': '要搜索的关键词'},
                    'engine': {
                        'type': 'string',
                        'enum': ['google', 'bing', 'baidu', 'duckduckgo'],
                        'description': '搜索引擎，默认 google，支持 google、bing、baidu、duckduckgo。',
                        'default': 'google',
                    },
                },
                'required': ['query'],
            },
        },
    },
]

# ── 浏览器页面操作工具（仅在浏览器打开后可用）─────────────────────────────────

BROWSER_PAGE_TOOLS: list[dict] = [
    {
        'type': 'function',
        'function': {
            'name': 'browse_read',
            'description': (
                '读取当前浏览器页面内容。支持三种模式：\n'
                "  'interactive' — 只列出可交互元素（ID、类型、标签文字），用于快速查找可操作元素\n"
                "  'text'        — 只显示页面正文（过滤空白）\n"
                "  'all'         — 正文 + 可交互元素（默认）\n"
                '在每次浏览器操作后调用以确认结果。'
            ),
            'parameters': {
                'type': 'object',
                'properties': {
                    'max_chars': {
                        'type': 'integer',
                        'description': '正文部分返回的最大字符数，默认 4000',
                        'default': 4000,
                    },
                    'mode': {
                        'type': 'string',
                        'enum': ['all', 'interactive', 'text'],
                        'description': "读取模式，默认 'all'",
                        'default': 'all',
                    },
                },
                'required': [],
            },
        },
    },
    {
        'type': 'function',
        'function': {
            'name': 'browse_click',
            'description': '点击页面中指定 ID 对应的可交互元素。',
            'parameters': {
                'type': 'object',
                'properties': {
                    'element_uuid': {
                        'type': 'string',
                        'description': 'browse_read 返回的元素 ID',
                    },
                },
                'required': ['element_uuid'],
            },
        },
    },
    {
        'type': 'function',
        'function': {
            'name': 'browse_fill',
            'description': '向指定 ID 对应的输入框（textbox / searchbox / combobox）填充文字。',
            'parameters': {
                'type': 'object',
                'properties': {
                    'element_uuid': {
                        'type': 'string',
                        'description': 'browse_read 返回的元素 ID',
                    },
                    'text': {
                        'type': 'string',
                        'description': '要填充的文字内容',
                    },
                },
                'required': ['element_uuid', 'text'],
            },
        },
    },
    {
        'type': 'function',
        'function': {
            'name': 'browse_press',
            'description': '向指定 ID 元素发送按键',
            'parameters': {
                'type': 'object',
                'properties': {
                    'element_uuid': {
                        'type': 'string',
                        'description': 'browse_read 返回的元素 ID',
                    },
                    'key': {
                        'type': 'string',
                        'description': '按键名称，如 Enter、Tab、Escape、ArrowDown 等',
                    },
                },
                'required': ['element_uuid', 'key'],
            },
        },
    },
    {
        'type': 'function',
        'function': {
            'name': 'browse_find',
            'description': '在当前页面中搜索包含指定文字的可见元素，返回匹配元素的选择器和文字片段。',
            'parameters': {
                'type': 'object',
                'properties': {
                    'text': {'type': 'string', 'description': '要搜索的文字'},
                    'max_results': {
                        'type': 'integer',
                        'description': '最多返回的结果数，默认 10',
                        'default': 10,
                    },
                },
                'required': ['text'],
            },
        },
    },
    {
        'type': 'function',
        'function': {
            'name': 'browse_pdf',
            'description': '将当前浏览器页面导出为 PDF 文件。',
            'parameters': {
                'type': 'object',
                'properties': {
                    'save_dir': {
                        'type': 'string',
                        'description': 'PDF 保存目录，默认为工作目录',
                    },
                },
                'required': [],
            },
        },
    },
    {
        'type': 'function',
        'function': {
            'name': 'browse_eval',
            'description': (
                '在当前浏览器页面中执行 JavaScript 表达式，返回执行结果。\n'
                '- 不要使用 return 语句。\n'
                '- 多步逻辑须用 IIFE 包裹。\n'
                '- 异步操作用 async IIF。\n'
            ),
            'parameters': {
                'type': 'object',
                'properties': {
                    'script': {'type': 'string', 'description': '要执行的 JavaScript 表达式'},
                },
                'required': ['script'],
            },
        },
    },
    {
        'type': 'function',
        'function': {
            'name': 'browse_wait_for_navigation',
            'description': '等待当前页面导航完成。在页面跳转时调用以使页面加载完成后再进行其他操作。',
            'parameters': {
                'type': 'object',
                'properties': {
                    'timeout': {
                        'type': 'integer',
                        'description': '最大等待时间（秒）',
                        'default': get_config()['wait'],
                    },
                    'state': {
                        'type': 'string',
                        'enum': ['load', 'domcontentloaded', 'networkidle'],
                        'description': "等待的加载状态，'load' 等待 load 事件，'domcontentloaded' 等待 DOM 解析完成，'networkidle' 等待网络空闲",
                        'default': 'networkidle'
                    }
                },
                'required': []
            },
        },
    },
    {
        'type': 'function',
        'function': {
            'name': 'browse_hover',
            'description': '将鼠标悬停在指定 ID 对应的元素上，触发 hover 事件。',
            'parameters': {
                'type': 'object',
                'properties': {
                    'element_uuid': {
                        'type': 'string',
                        'description': 'browse_read 返回的元素 ID',
                    },
                },
                'required': ['element_uuid'],
            },
        },
    },
    {
        'type': 'function',
        'function': {
            'name': 'browse_select',
            'description': (
                '在指定 ID 对应的原生 <select> 下拉框中选择选项。'
                'value 可以是选项的显示文字（label）、value 属性值，或数字索引（如 \'0\'、\'1\'）。'
                '对于非原生 select（如自定义下拉组件），应使用 browse_click 配合 browse_hover。'
            ),
            'parameters': {
                'type': 'object',
                'properties': {
                    'element_uuid': {
                        'type': 'string',
                        'description': 'browse_read 返回的元素 ID',
                    },
                    'value': {
                        'type': 'string',
                        'description': '要选择的选项，可以是显示文字、value 属性或数字索引',
                    },
                },
                'required': ['element_uuid', 'value'],
            },
        },
    },
    {
        'type': 'function',
        'function': {
            'name': 'browse_get_url',
            'description': '返回当前页面的 URL 和标题。',
            'parameters': {
                'type': 'object',
                'properties': {},
                'required': [],
            },
        },
    },
    {
        'type': 'function',
        'function': {
            'name': 'browse_upload',
            'description': (
                '向指定 ID 对应的文件选择框上传一个或多个本地文件。\n'
                '路径须为绝对路径或相对于当前工作目录的路径。'
            ),
            'parameters': {
                'type': 'object',
                'properties': {
                    'element_uuid': {
                        'type': 'string',
                        'description': 'browse_read 返回的文件选择框元素 ID',
                    },
                    'file_paths': {
                        'oneOf': [
                            {'type': 'string'},
                            {'type': 'array', 'items': {'type': 'string'}},
                        ],
                        'description': '要上传的本地文件路径，单文件传字符串，多文件传列表',
                    },
                },
                'required': ['element_uuid', 'file_paths'],
            },
        },
    },
    {
        'type': 'function',
        'function': {
            'name': 'browse_download',
            'description': (
                '点击指定 ID 对应的下载链接或按钮，等待浏览器下载完成，'
                '并将文件保存到指定目录。\n'
                '下载超时默认 60 秒，下载大文件前可先用 set_wait(target=\'download\') 调高。'
            ),
            'parameters': {
                'type': 'object',
                'properties': {
                    'element_uuid': {
                        'type': 'string',
                        'description': 'browse_read 返回的下载链接/按钮 ID',
                    },
                    'save_dir': {
                        'type': 'string',
                        'description': '文件保存目录，默认为当前工作目录',
                    },
                },
                'required': ['element_uuid'],
            },
        },
    },
    {
        'type': 'function',
        'function': {
            'name': 'browse_scroll',
            'description': '滚动页面或指定元素。支持方向: up / down / left / right。',
            'parameters': {
                'type': 'object',
                'properties': {
                    'direction': {
                        'type': 'string',
                        'enum': ['down', 'up', 'left', 'right'],
                        'description': "滚动方向，默认 'down'",
                        'default': 'down',
                    },
                    'amount': {
                        'type': 'integer',
                        'description': '滚动像素数，默认 500',
                        'default': 500,
                    },
                    'element_uuid': {
                        'type': 'string',
                        'description': '可选。若传入则滚动该元素内部容器，否则滚动整个页面',
                    },
                },
                'required': [],
            },
        },
    },
    {
        'type': 'function',
        'function': {
            'name': 'browse_close',
            'description': '关闭浏览器。',
            'parameters': {
                'type': 'object',
                'properties': {},
                'required': [],
            },
        },
    },
]


# ── 条件检查函数 ────────────────────────────────────────────────────────────

def is_browser_base_available() -> bool:
    """浏览器基础工具始终可用。"""
    return True


def is_browser_page_available() -> bool:
    """
    浏览器页面操作工具仅在浏览器打开后可用。
    此函数会被 Host 层调用以决定是否包含这些工具。
    """
    # 延迟导入以避免循环依赖
    try:
        from server.servers.browser import is_browser_open
        return is_browser_open()
    except ImportError:
        return False


# ── 完整工具列表（向后兼容）─────────────────────────────────────────────────

ALL_BROWSER_TOOLS: list[dict] = BROWSER_BASE_TOOLS + BROWSER_PAGE_TOOLS


# ── 获取可用浏览器工具函数 ──────────────────────────────────────────────────

def get_browser_tools(browser_open: bool = False) -> list[dict]:
    """根据浏览器状态获取可用的浏览器工具列表。
    
    Args:
        browser_open: 浏览器是否已打开
        
    Returns:
        可用的浏览器工具列表
    """
    tools = BROWSER_BASE_TOOLS.copy()
    if browser_open:
        tools = tools + BROWSER_PAGE_TOOLS
    return tools
