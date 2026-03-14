from config import *

TOOLS: list[dict] = [
    {
        "type": "function",
        "function": {
            "name": "system_command",
            "description": "在用户的终端执行命令，例如 dir/ls、mkdir 等。",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "要执行的终端命令"},
                    "properties": {
                        "command": {"type": "string", "description": "要执行的终端命令"},
                        "inputs": {
                            "type": ["string", "array"],
                            "items": {"type": "string"},
                            "description": "可选。如果命令需要交互式输入（如确认、输入参数），在此提供。若是列表则按顺序输入。"
                        }
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
            "description": "用新内容整体覆盖写入指定文件（创建或覆盖）。将文件完整内容作为 content 参数传入。",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {"type": "string", "description": "文件的绝对路径（含扩展名）"},
                    "content": {"type": "string", "description": "写入文件的完整内容"},
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
            "description": "对文件的部分内容进行精确替换。将要被替换的旧文本和替换后的新文本分别作为参数传入。旧文本必须与文件中的内容完全一致。",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {"type": "string", "description": "文件的绝对路径（含扩展名）"},
                    "old_text": {"type": "string", "description": "文件中要被替换的原始文本，必须与文件内容完全一致"},
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
            "description": "读取并返回指定文件的完整内容。",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {"type": "string", "description": "文件的绝对路径（含扩展名）"},
                    "encoding": {"type": "string", "description": "文件编码", "default": get_config()['encoding']},
                },
                "required": ["file_path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "change_directory",
            "description": "切换当前工作目录（支持相对路径或绝对路径）。",
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
            "name": "finish",
            "description": "完成所有工作，向用户交付成果并结束自动执行阶段。",
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
                    "url": {"type": "string", "description": "要打开的完整 URL"},
                },
                "required": ["url"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "browse_search",
            "description": "使用搜索引擎搜索关键词，直接跳转到搜索结果页。支持 google、bing、baidu、duckduckgo，默认 google。",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "搜索关键词"},
                    "engine": {
                        "type": "string",
                        "enum": ["google", "bing", "baidu", "duckduckgo"],
                        "description": "搜索引擎，默认 google",
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
            "description": "读取当前浏览器页面的文字内容及可交互元素列表。建议在每次浏览器操作后调用以确认结果。",
            "parameters": {
                "type": "object",
                "properties": {
                    "max_chars": {
                        "type": "integer",
                        "description": "返回内容的最大字符数，默认 4000",
                        "default": 4000,
                    },
                },
                "required": [],
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
            "name": "browse_download",
            "description": "通过浏览器下载文件（保留登录态 Cookie），保存到工作目录或指定目录。",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "文件下载 URL"},
                    "save_dir": {
                        "type": "string",
                        "description": "保存目录，默认为工作目录",
                    },
                },
                "required": ["url"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "browse_upload",
            "description": "向页面的文件输入框上传本地文件。",
            "parameters": {
                "type": "object",
                "properties": {
                    "selector": {"type": "string", "description": "文件输入框的 CSS 选择器"},
                    "file_path": {"type": "string", "description": "本地文件的绝对路径"},
                },
                "required": ["selector", "file_path"],
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
            "description": "在当前浏览器页面中执行 JavaScript 表达式，返回执行结果。",
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
            "description": "等待当前页面导航完成（例如点击链接、提交表单或执行了可能跳转的 JavaScript 后）。\n建议在调用可能触发页面跳转的 browse_eval 之后调用此工具，以确保新页面完全加载后再进行读取或其他操作。",
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
            "name": "browse_switch",
            "description": "切换到指定编号的标签页。标签页编号可在 browse_read 返回的标签页列表中查看。",
            "parameters": {
                "type": "object",
                "properties": {
                    "index": {"type": "integer", "description": "目标标签页的编号"},
                },
                "required": ["index"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "browse_close",
            "description": "关闭浏览器及 Playwright 实例。",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    },
]