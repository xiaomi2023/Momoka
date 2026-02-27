from config import get_config
from logger import log, chat_log
from openai import OpenAI

# ── Tool 定义（JSON Function Call 格式）────────────────────────────────────
TOOLS: list[dict] = [
    {
        "type": "function",
        "function": {
            "name": "system_command",
            "description": "在用户的 CMD 终端执行命令，例如 dir、mkdir、copy 等。",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "要执行的终端命令"},
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
                    "file_path": {"type": "string", "description": "文件绝对路径（含扩展名）"},
                    "content": {"type": "string", "description": "写入文件的完整内容"},
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
                    "file_path": {"type": "string", "description": "文件绝对路径（含扩展名）"},
                    "old_text": {"type": "string", "description": "文件中要被替换的原始文本，必须与文件内容完全一致"},
                    "new_text": {"type": "string", "description": "替换后的新文本"},
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
                    "file_path": {"type": "string", "description": "文件绝对路径（含扩展名）"},
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
            "name": "output",
            "description": "向用户输出消息或工作成果。",
            "parameters": {
                "type": "object",
                "properties": {
                    "message": {"type": "string", "description": "要发送给用户的内容"},
                },
                "required": ["message"],
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
            "description": "将当前浏览器页面导出为 PDF 文件（仅 headless 模式支持）。",
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


class Bot:
    def __init__(self, bot_name: str = 'null'):
        self.bot_name = bot_name
        cfg = get_config()
        self.openai = OpenAI(api_key=cfg['api_key'], base_url=cfg['base_url'])
        self.history = [{'role': 'system', 'content': 'You are a helpful assistant'}]
        # 与 history 等长的元数据列表。
        # 每个元素是一个字典，目前只用 'file_contents' 键：
        #   {'file_contents': {filename: content_str, ...}}
        # 普通消息对应的元数据为空字典 {}。
        self._meta: list[dict] = [{}]

    def message(self, message: str, role: str = 'user',
                file_contents: dict[str, str] | None = None,
                use_tools: bool = False) -> dict:
        """向模型发送消息，返回响应字典。

        Args:
            message:       发送给模型的文本。
            role:          消息角色，默认 'user'。
            file_contents: 本条消息中包含的文件内容，格式为 {filename: content}。
            use_tools:     是否传入 TOOLS 列表启用 function calling。

        Returns:
            dict，包含：
                'content': str       —— 模型的文本回复（可能为空字符串）
                'tool_calls': list   —— tool_call 对象列表（可能为空列表）
        """
        cfg = get_config()
        log_prefix = f'chat with {cfg["model"]} ({cfg["base_url"]}) as {self.bot_name}'
        log(f'{log_prefix} | input: {message}')

        kwargs: dict = dict(
            model=cfg['model'],
            messages=self.history + [{'role': role, 'content': message}],
            stream=False,
        )
        if use_tools:
            kwargs['tools'] = TOOLS
            kwargs['tool_choice'] = 'auto'

        # noinspection PyTypeChecker
        response = self.openai.chat.completions.create(**kwargs)
        choice = response.choices[0].message

        text_content: str = choice.content or ''
        tool_calls: list = choice.tool_calls or []

        log(f'{log_prefix} | output text: {text_content}')
        if tool_calls:
            for tc in tool_calls:
                log(f'{log_prefix} | tool_call: {tc.function.name}({tc.function.arguments})')

        # ── 将本轮对话写入历史（assistant 消息需含 tool_calls 字段）──────────
        assistant_msg: dict = {'role': 'assistant', 'content': text_content}
        if tool_calls:
            assistant_msg['tool_calls'] = [
                {
                    'id': tc.id,
                    'type': 'function',
                    'function': {'name': tc.function.name, 'arguments': tc.function.arguments},
                }
                for tc in tool_calls
            ]

        self.history.extend([
            {'role': role, 'content': message},
            assistant_msg,
        ])
        self._meta.append({'file_contents': file_contents or {}})
        self._meta.append({})  # assistant 消息无文件内容

        chat_log(f'[{self.bot_name}] USER: {message}')
        chat_log(f'[{self.bot_name}] ASSISTANT TEXT: {text_content}')
        if tool_calls:
            chat_log(f'[{self.bot_name}] TOOL_CALLS: {[tc.function.name for tc in tool_calls]}')
        chat_log(f'[{self.bot_name}] HISTORY SNAPSHOT: {self.history}')

        return {
            'content': text_content,
            'tool_calls': tool_calls,
        }

    def add_tool_result(self, tool_call_id: str, result: str):
        """将工具执行结果追加到对话历史，供下一次 message() 使用。"""
        self.history.append({
            'role': 'tool',
            'tool_call_id': tool_call_id,
            'content': result,
        })
        self._meta.append({})

    def resume(self, use_tools: bool = True) -> dict:
        """工具执行完毕后，直接用当前历史继续推理，不插入任何 user 消息。

        调用方应在所有 add_tool_result() 完成后调用此方法。
        """
        cfg = get_config()
        log_prefix = f'chat with {cfg["model"]} ({cfg["base_url"]}) as {self.bot_name}'
        log(f'{log_prefix} | resume')

        kwargs: dict = dict(model=cfg['model'], messages=self.history, stream=False)
        if use_tools:
            kwargs['tools'] = TOOLS
            kwargs['tool_choice'] = 'auto'

        # noinspection PyTypeChecker
        response = self.openai.chat.completions.create(**kwargs)
        choice = response.choices[0].message

        text_content: str = choice.content or ''
        tool_calls: list = choice.tool_calls or []

        log(f'{log_prefix} | resume output text: {text_content}')
        if tool_calls:
            for tc in tool_calls:
                log(f'{log_prefix} | tool_call: {tc.function.name}({tc.function.arguments})')

        assistant_msg: dict = {'role': 'assistant', 'content': text_content}
        if tool_calls:
            assistant_msg['tool_calls'] = [
                {
                    'id': tc.id,
                    'type': 'function',
                    'function': {'name': tc.function.name, 'arguments': tc.function.arguments},
                }
                for tc in tool_calls
            ]

        self.history.append(assistant_msg)
        self._meta.append({})

        chat_log(f'[{self.bot_name}] RESUME ASSISTANT TEXT: {text_content}')
        if tool_calls:
            chat_log(f'[{self.bot_name}] RESUME TOOL_CALLS: {[tc.function.name for tc in tool_calls]}')

        return {'content': text_content, 'tool_calls': tool_calls}

    def set_system(self, system: str):
        """设置或替换 system 提示词。"""
        if self.history[0]['role'] == 'system':
            self.history[0]['content'] = system
        else:
            self.history.insert(0, {'role': 'system', 'content': system})
            self._meta.insert(0, {})

    def collapse_file_in_history(self, filename: str) -> int:
        """将对话历史中除最后一次之外、所有包含指定文件内容的消息折叠。

        通过 _meta 中记录的原始文件内容精确定位并替换，无需正则匹配。
        返回折叠的消息条数。
        """
        placeholder = f'[文件内容已折叠：{filename}]'
        hits = [
            i for i, m in enumerate(self._meta)
            if filename in m.get('file_contents', {})
        ]
        if len(hits) <= 1:
            return 0

        collapsed_count = 0
        for i in hits[:-1]:
            content = self._meta[i]['file_contents'][filename]
            original = self.history[i].get('content')
            if original and isinstance(original, str):
                new_content = original.replace(content, placeholder, 1)
                if new_content != original:
                    self.history[i]['content'] = new_content
                    collapsed_count += 1
                    log(f'bot.collapse_file_in_history | 折叠历史[{i}]中的文件：{filename}')
            del self._meta[i]['file_contents'][filename]

        return collapsed_count


def chat(question: str, role: str = 'user') -> str:
    """快捷函数：创建一次性 Bot 并发送单条消息（不使用 tools）。"""
    result = Bot().message(question, role, use_tools=False)
    return result['content']