from config import *

TOOLS: list[dict] = [
    {
        "type": "function",
        "function": {
            "name": "system_command",
            "description": "在用户的终端执行命令。",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "要执行的终端命令"},
                    "inputs": {
                        "type": ["string", "array"],
                        "items": {"type": "string"},
                        "description": "可选。如果命令需要交互式输入（如确认、输入参数），在此提供。若是列表则按顺序输入。"
                    }
                },
                "required": ["command"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "edit_file",
            "description": "用新内容覆盖指定文件（文件不存在则新建文件）。",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {"type": "string", "description": "文件的绝对路径（含扩展名）"},
                    "content": {"type": "string", "description": "写入文件的内容"},
                    "encoding": {"type": "string", "description": "文件编码", "default": get_config()['encoding']},
                },
                "required": ["file_path", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "replace_file",
            "description": "对文件的部分内容进行替换。",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {"type": "string", "description": "文件的绝对路径（含扩展名）"},
                    "old_text": {"type": "string", "description": "要被替换的原始文本"},
                    "new_text": {"type": "string", "description": "替换后的新文本"},
                    "encoding": {"type": "string", "description": "文件编码", "default": get_config()['encoding']},
                },
                "required": ["file_path", "old_text", "new_text"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": (
                "读取并返回指定文件的内容。\n"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {"type": "string", "description": "文件的绝对路径（含扩展名）"},
                    "encoding": {"type": "string", "description": "文件编码", "default": get_config()['encoding']},
                    "mode": {
                        "type": "string",
                        "enum": ["doc"],
                        "description": "可选。'doc'：以 Markdown 格式读取 .docx 文件内容。",
                    },
                },
                "required": ["file_path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_sheet",
            "description": (
                "读取 Sheet 文件（.xlsx/.xls）的内容。\n"
                "不指定 sheet_name 时返回所有 Sheet 名称列表并读取第一个 Sheet。\n"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {"type": "string", "description": "Sheet 文件的绝对路径（含扩展名）"},
                    "sheet_name": {
                        "type": "string",
                        "description": "可选。要读取的 Sheet 名称。",
                    },
                    "sheet_mode": {
                        "type": "string",
                        "enum": ["all", "csv_only", "formula_only"],
                        "description": "读取模式：'all' 返回 CSV + 公式（默认），'csv_only' 只返回 CSV，'formula_only' 只返回公式。",
                        "default": "all",
                    },
                    "range": {
                        "type": "string",
                        "description": "可选。读取范围，如 'A1:D20'。",
                    },
                },
                "required": ["file_path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "change_directory",
            "description": "切换当前工作目录。",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "目标目录路径"},
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "ask_user",
            "description": "在有问题时向用户提问，等待用户回复后继续。",
            "parameters": {
                "type": "object",
                "properties": {
                    "question": {"type": "string", "description": "向用户提出的问题"},
                },
                "required": ["question"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "set_wait",
            "description": "设置操作的最大超时时长（秒）。默认为 10 秒。",
            "parameters": {
                "type": "object",
                "properties": {
                    "seconds": {"type": "integer", "description": "超时时长（秒）"},
                },
                "required": ["seconds"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "set_read_limits",
            "description": (
                "设置 read_file 工具允许读取的文件最大行数和最大体积。"
                "默认限制为 1000 行 / 100 KB。上限分别为 50000 行 / 5120 KB（5 MB），超出部分自动截断到上限。"
                "当需要读取较大文件时，可先调用此工具调高限制，再调用 read_file。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "max_lines": {
                        "type": "integer",
                        "description": "允许读取的最大行数（上限 50000）",
                    },
                    "max_size_kb": {
                        "type": "integer",
                        "description": "允许读取的最大文件体积，单位 KB（上限 5120）",
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_skill",
            "description": (
                "在需要时加载 Agent Skills 标准格式的skill文件（SKILL.md）或skill内的脚本/资源文件。"
                "skill目录结构: <name>/SKILL.md、scripts/（可执行脚本）、"
                "references/（参考文档）、assets/（模板及二进制资源）。"
                "需要执行脚本或读取额外文档时，用 resource='scripts/xxx.py' 等再次调用。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "skill_name": {
                        "type": "string",
                        "description": "skill名称",
                    },
                    "resource": {
                        "type": "string",
                        "description": (
                            "可选。skill目录内的相对路径。"
                        ),
                    },
                },
                "required": ["skill_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "finish",
            "description": "结束工作并向用户交付。",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    },
    # ── 浏览器指令 ────────────────────────────────────────────────────────
    {
        "type": "function",
        "function": {
            "name": "browse_open",
            "description": "用 Chromium 浏览器打开指定网页。",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "要打开的网页 URL"},
                },
                "required": ["url"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "browse_search",
            "description": "使用搜索引擎搜索关键词。",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "要搜索的关键词"},
                    "engine": {
                        "type": "string",
                        "enum": ["google", "bing", "baidu", "duckduckgo"],
                        "description": "搜索引擎，默认 google，支持 google、bing、baidu、duckduckgo。",
                        "default": "google",
                    },
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "browse_read",
            "description": (
                "读取当前浏览器页面内容。支持三种模式：\n"
                "  'interactive' — 只列出可交互元素（ID、类型、标签文字），用于快速查找可操作元素\n"
                "  'text'        — 只显示页面正文（过滤空白）\n"
                "  'all'         — 正文 + 可交互元素（默认）\n"
                "在每次浏览器操作后调用以确认结果。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "max_chars": {
                        "type": "integer",
                        "description": "正文部分返回的最大字符数，默认 4000",
                        "default": 4000,
                    },
                    "mode": {
                        "type": "string",
                        "enum": ["all", "interactive", "text"],
                        "description": "读取模式，默认 'all'",
                        "default": "all",
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "browse_click",
            "description": (
                "点击页面中指定 ID 对应的可交互元素。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "element_uuid": {
                        "type": "string",
                        "description": "browse_read 返回的元素 ID",
                    },
                },
                "required": ["element_uuid"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "browse_fill",
            "description": (
                "向指定 ID 对应的输入框（textbox / searchbox / combobox）填充文字。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "element_uuid": {
                        "type": "string",
                        "description": "browse_read 返回的元素 ID",
                    },
                    "text": {
                        "type": "string",
                        "description": "要填充的文字内容",
                    },
                },
                "required": ["element_uuid", "text"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "browse_press",
            "description": (
                "向指定 ID 元素发送按键"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "element_uuid": {
                        "type": "string",
                        "description": "browse_read 返回的元素 ID",
                    },
                    "key": {
                        "type": "string",
                        "description": "按键名称，如 Enter、Tab、Escape、ArrowDown 等",
                    },
                },
                "required": ["element_uuid", "key"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "browse_find",
            "description": "在当前页面中搜索包含指定文字的可见元素，返回匹配元素的选择器和文字片段。",
            "parameters": {
                "type": "object",
                "properties": {
                    "text": {"type": "string", "description": "要搜索的文字"},
                    "max_results": {
                        "type": "integer",
                        "description": "最多返回的结果数，默认 10",
                        "default": 10,
                    },
                },
                "required": ["text"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "browse_pdf",
            "description": "将当前浏览器页面导出为 PDF 文件。",
            "parameters": {
                "type": "object",
                "properties": {
                    "save_dir": {
                        "type": "string",
                        "description": "PDF 保存目录，默认为工作目录",
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "browse_eval",
            "description": (
                "在当前浏览器页面中执行 JavaScript 表达式，返回执行结果。\n"
                "- 不要使用 return 语句。\n"
                "- 多步逻辑须用 IIFE 包裹。\n"
                "- 异步操作用 async IIF。\n"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "script": {"type": "string", "description": "要执行的 JavaScript 表达式"},
                },
                "required": ["script"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "browse_wait_for_navigation",
            "description": "等待当前页面导航完成。在页面跳转时调用以使页面加载完成后再进行其他操作。",
            "parameters": {
                "type": "object",
                "properties": {
                    "timeout": {
                        "type": "integer",
                        "description": "最大等待时间（秒）",
                        "default": get_config()['wait'],
                    },
                    "state": {
                        "type": "string",
                        "enum": ["load", "domcontentloaded", "networkidle"],
                        "description": "等待的加载状态，'load' 等待 load 事件，'domcontentloaded' 等待 DOM 解析完成，'networkidle' 等待网络空闲",
                        "default": "networkidle"
                    }
                },
                "required": []
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "browse_hover",
            "description": (
                "将鼠标悬停在指定 ID 对应的元素上，触发 hover 事件。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "element_uuid": {
                        "type": "string",
                        "description": "browse_read 返回的元素 ID",
                    },
                },
                "required": ["element_uuid"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "browse_select",
            "description": (
                "在指定 ID 对应的原生 <select> 下拉框中选择选项。"
                "value 可以是选项的显示文字（label）、value 属性值，或数字索引（如 '0'、'1'）。"
                "对于非原生 select（如自定义下拉组件），应使用 browse_click 配合 browse_hover。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "element_uuid": {
                        "type": "string",
                        "description": "browse_read 返回的元素 ID",
                    },
                    "value": {
                        "type": "string",
                        "description": "要选择的选项，可以是显示文字、value 属性或数字索引",
                    },
                },
                "required": ["element_uuid", "value"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "browse_get_url",
            "description": (
                "返回当前页面的 URL 和标题。"
            ),
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "browse_upload",
            "description": (
                "向指定 ID 对应的文件选择框上传一个或多个本地文件。\n"
                "路径须为绝对路径或相对于当前工作目录的路径。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "element_uuid": {
                        "type": "string",
                        "description": "browse_read 返回的文件选择框元素 ID",
                    },
                    "file_paths": {
                        "oneOf": [
                            {"type": "string"},
                            {"type": "array", "items": {"type": "string"}},
                        ],
                        "description": "要上传的本地文件路径，单文件传字符串，多文件传列表",
                    },
                },
                "required": ["element_uuid", "file_paths"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "browse_download",
            "description": (
                "点击指定 ID 对应的下载链接或按钮，等待浏览器下载完成，"
                "并将文件保存到指定目录。\n"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "element_uuid": {
                        "type": "string",
                        "description": "browse_read 返回的下载链接/按钮 ID",
                    },
                    "save_dir": {
                        "type": "string",
                        "description": "文件保存目录，默认为当前工作目录",
                    },
                },
                "required": ["element_uuid"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "browse_scroll",
            "description": (
                "滚动页面或指定元素。支持方向: up / down / left / right。\n"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "direction": {
                        "type": "string",
                        "enum": ["down", "up", "left", "right"],
                        "description": "滚动方向，默认 'down'",
                        "default": "down",
                    },
                    "amount": {
                        "type": "integer",
                        "description": "滚动像素数，默认 500",
                        "default": 500,
                    },
                    "element_uuid": {
                        "type": "string",
                        "description": "可选。若传入则滚动该元素内部容器，否则滚动整个页面",
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "browse_close",
            "description": "关闭浏览器。",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    },
]