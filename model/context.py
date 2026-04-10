"""
model/context.py —— 对话历史与上下文管理。

负责维护 history 列表、_meta 元数据、skill 注入/清除、
历史修复（repair）和文件内容折叠（collapse）。
"""

from logger import log


class Context:
    def __init__(self, base_system: str = 'You are a helpful assistant'):
        self._base_system: str = base_system
        self._injected_skills: dict[str, str] = {}
        self.history: list[dict] = [{'role': 'system', 'content': base_system}]
        # 与 history 等长的元数据列表，记录每条消息携带的文件内容
        self._meta: list[dict] = [{}]

    # ── System Prompt ─────────────────────────────────────────────────────

    def set_system(self, system: str):
        """设置或替换 system 提示词（同时重置 base system）。"""
        self._base_system = system
        self._apply_system()

    def inject_skill(self, skill_name: str, skill_content: str):
        """将 skill 内容追加到 system prompt。"""
        self._injected_skills[skill_name] = skill_content
        self._apply_system()
        log(f'context.inject_skill | 注入skill: {skill_name}')

    def clear_skills(self):
        """移除所有已注入的 skill，将 system 恢复为 base system。"""
        if not self._injected_skills:
            return
        names = list(self._injected_skills.keys())
        self._injected_skills.clear()
        self._apply_system()
        log(f'context.clear_skills | 已移除skills: {names}')

    def _apply_system(self):
        """将 base system + 所有已注入 skill 合并写入 history[0]。"""
        parts = [self._base_system]
        for name, content in self._injected_skills.items():
            parts.append(f'\n<skill: {name}>\n{content}\n</skill>')
        full_system = ''.join(parts)
        if self.history[0]['role'] == 'system':
            self.history[0]['content'] = full_system
        else:
            self.history.insert(0, {'role': 'system', 'content': full_system})
            self._meta.insert(0, {})

    # ── History 写入 ──────────────────────────────────────────────────────

    def insert_preset_conversations(self, conversations: list[dict]):
        """在 system 提示词后插入预设对话。

        Args:
            conversations: 对话列表，每个元素为 {'role': 'user'|'assistant', 'content': str}
                          或 assistant 的 tool_calls 格式。
        """
        if not conversations:
            return

        insert_position = 1  # system 消息之后
        for conv in conversations:
            role = conv.get('role')
            if role == 'user':
                self.history.insert(insert_position, {'role': 'user', 'content': conv['content']})
                self._meta.insert(insert_position, {'file_contents': {}})
                insert_position += 1
            elif role == 'assistant':
                assistant_msg = {'role': 'assistant', 'content': conv.get('content', '')}
                if 'tool_calls' in conv:
                    assistant_msg['tool_calls'] = conv['tool_calls']
                self.history.insert(insert_position, assistant_msg)
                self._meta.insert(insert_position, {})
                insert_position += 1
            else:
                log(f'context.insert_preset_conversations | 跳过不支持的角色: {role}')

        log(f'context.insert_preset_conversations | 插入 {len(conversations)} 条预设对话')

    def append_user(self, message: str, file_contents: dict[str, str] | None = None):
        """追加一条 user 消息到历史。"""
        self.history.append({'role': 'user', 'content': message})
        self._meta.append({'file_contents': file_contents or {}})

    def append_assistant(self, text_content: str, tool_calls: list):
        """追加一条 assistant 消息到历史。"""
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

    def append_assistant_raw(self, assistant_msg: dict):
        """追加已序列化好的 assistant 消息（resume 路径使用）。"""
        self.history.append(assistant_msg)
        self._meta.append({})

    def add_tool_result(self, tool_call_id: str, result: str,
                        file_contents: dict[str, str] | None = None):
        """追加工具执行结果到历史。"""
        self.history.append({
            'role': 'tool',
            'tool_call_id': tool_call_id,
            'content': result,
        })
        self._meta.append({'file_contents': file_contents or {}})

    # ── History 修复与折叠 ────────────────────────────────────────────────

    def repair_history(self) -> int:
        """检测并修复孤儿 tool_calls 消息（无对应 tool_result 的情况）。

        Returns:
            修复的孤儿 tool_call 数量（0 表示无需修复）。
        """
        repaired = 0
        i = 0
        while i < len(self.history):
            msg = self.history[i]
            if msg.get('role') == 'assistant' and msg.get('tool_calls'):
                expected_ids = {tc['id'] for tc in msg['tool_calls']}
                j = i + 1
                covered_ids: set[str] = set()
                while j < len(self.history) and self.history[j].get('role') == 'tool':
                    covered_ids.add(self.history[j].get('tool_call_id', ''))
                    j += 1
                missing_ids = expected_ids - covered_ids
                if missing_ids:
                    placeholder_msgs = []
                    placeholder_metas = []
                    for tc_id in missing_ids:
                        placeholder_msgs.append({
                            'role': 'tool',
                            'tool_call_id': tc_id,
                            'content': '（已中断，工具未执行）',
                        })
                        placeholder_metas.append({})
                        repaired += 1
                    self.history[i + 1:i + 1] = placeholder_msgs
                    self._meta[i + 1:i + 1] = placeholder_metas
                    log(f'context.repair_history | 补全 {len(missing_ids)} 个孤儿 tool_result: {missing_ids}')
                    i = j + len(missing_ids)
                else:
                    i = j
            else:
                i += 1
        return repaired

    def collapse_file_in_history(self, filename: str) -> int:
        """将历史中除最后一次之外、所有包含指定文件内容的消息折叠。

        Returns:
            折叠的消息条数。
        """
        placeholder = f'[Collapse file contents: {filename}]'
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
                    log(f'context.collapse_file_in_history | 折叠历史[{i}]中的文件: {filename}')
            del self._meta[i]['file_contents'][filename]

        return collapsed_count