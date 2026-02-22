from config import get_config
from logger import log, chat_log
from openai import OpenAI
import re


class Bot:
    def __init__(self, bot_name: str = 'null'):
        self.bot_name = bot_name
        cfg = get_config()
        self.openai = OpenAI(api_key=cfg['api_key'], base_url=cfg['base_url'])
        self.history = [{'role': 'system', 'content': 'You are a helpful assistant'}]

    def message(self, message: str, role: str = 'user') -> str:
        """向模型发送消息，返回回复内容，并将本轮对话追加到历史记录。"""

        cfg = get_config()
        log_prefix = f'chat with {cfg["model"]} ({cfg["base_url"]}) as {self.bot_name}'

        log(f'{log_prefix} | input: {message}')
        # noinspection PyTypeChecker
        response = self.openai.chat.completions.create(
            model=cfg['model'],
            messages=self.history + [{'role': role, 'content': message}],
            stream=False
        )
        result = response.choices[0].message.content
        log(f'{log_prefix} | output:\n{result}')

        # 将本轮对话写入历史
        self.history.extend([
            {'role': 'user', 'content': message},
            {'role': 'assistant', 'content': result},
        ])

        # 对话历史单独写入 chat_history_log.txt
        chat_log(f'[{self.bot_name}] USER: {message}')
        chat_log(f'[{self.bot_name}] ASSISTANT: {result}')
        chat_log(f'[{self.bot_name}] HISTORY SNAPSHOT: {self.history}')

        return result

    def set_system(self, system: str):
        """设置或替换 system 提示词。"""
        if self.history[0]['role'] == 'system':
            self.history[0]['content'] = system
        else:
            self.history.insert(0, {'role': 'system', 'content': system})

    def collapse_file_in_history(self, filename: str) -> int:
        """
        将对话历史中除最后一次之外、所有包含指定文件内容的消息折叠。

        匹配规则：消息中包含形如
            成功打开文件：{filename}\n{filename}:\n{内容}
        或
            文件编辑完成，以下为 {filename} 的新内容：\n{内容}
        的片段，将其中的"内容"部分替换为折叠占位符。

        返回折叠的消息条数。
        """
        # 用文件名构造匹配模式（转义路径中的特殊字符）
        esc = re.escape(filename)

        # 两种出现模式：
        #   READ  → "成功打开文件：<path>\n<path>:\n<content>"
        #   EDIT  → "文件编辑完成，以下为 <path> 的新内容：\n<content>"
        patterns = [
            # READ 模式：文件名后跟冒号换行，内容直到字符串末尾或下一个明显分隔
            re.compile(
                r'(成功打开文件：' + esc + r'\n' + esc + r':\n)(.+)',
                re.DOTALL
            ),
            # EDIT 模式
            re.compile(
                r'(文件编辑完成，以下为 ' + esc + r' 的新内容：\n)(.+)',
                re.DOTALL
            ),
        ]

        placeholder = f'[文件内容已折叠：{filename}]'

        # 找出所有命中的 (消息索引, pattern索引, match对象)
        hits: list[tuple[int, re.Pattern, re.Match]] = []
        for i, turn in enumerate(self.history):
            content = turn.get('content', '')
            if not isinstance(content, str):
                continue
            for pat in patterns:
                m = pat.search(content)
                if m:
                    hits.append((i, pat, m))
                    break  # 一条消息只会命中一种模式

        if len(hits) <= 1:
            # 只有一次（或没有）→ 就是最新那次，不折叠
            return 0

        # 保留最后一次，折叠其余
        to_collapse = hits[:-1]
        collapsed_count = 0
        for (i, pat, _) in to_collapse:
            original = self.history[i]['content']
            new_content = pat.sub(lambda m: m.group(1) + placeholder, original)
            if new_content != original:
                self.history[i]['content'] = new_content
                collapsed_count += 1
                log(f'bot.collapse_file_in_history | 折叠历史[{i}]中的文件：{filename}')

        return collapsed_count


def chat(question: str, role: str = 'user') -> str:
    """快捷函数：创建一次性 Bot 并发送单条消息。"""
    return Bot().message(question, role)