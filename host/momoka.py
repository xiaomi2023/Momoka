"""
host/momoka.py —— Agent 编排器。

持有 Model 实例，负责 agent 循环（工具调用 → resume → 交还控制权）
以及 skill 的加载与清除。
"""

import json
import os
from dataclasses import dataclass

from logger import log
from model.model import Model
from server.router import execute_tool_calls
from host.prompt_builder import build_system_prompt
from server.tool_registry import get_available_tools


@dataclass
class SendResult:
    """Return result from send() method."""
    is_finish: bool          # Whether finish was called
    file_contents: dict      # Files read in this round
    input_tokens: int        # Input token count
    output_tokens: int       # Output token count
    round_count: int         # Number of conversation rounds


@dataclass
class SkillLoadResult:
    """Return result from load_skill() method."""
    success: bool            # Whether loading succeeded
    message: str             # Result message


@dataclass
class AgentLoopResult:
    """Agent loop execution result."""
    is_finish: bool          # Whether finish was called
    file_contents: dict      # Files read in this round
    input_tokens: int        # Input token count
    output_tokens: int       # Output token count
    round_count: int         # Number of conversation rounds


class Momoka:
    """Momoka agent orchestrator."""

    def __init__(self, user=None, call_wrapper=None):
        """
        Args:
            user: User instance, used for outputting logs
            call_wrapper: Optional call wrapper for showing spinners etc. during API calls.
                         Signature: wrapper(fn, *args, **kwargs) -> result
        """
        self._user = user
        self._model = Model(name='Momoka', user=user)
        self._model.set_system(build_system_prompt())
        self._call_wrapper = call_wrapper or (lambda fn, *a, **kw: fn(*a, **kw))

        # Load preset conversations
        self._load_preset_conversations()

        # Initialize MCP Client
        self._init_mcp_client()

    # ── Public API (called by user layer) ──────────────────────────────────

    def send(self, message: str,
             file_contents: dict[str, str] | None = None) -> SendResult:
        """Receive user message, start agent loop, return status when loop ends."""
        log(f'momoka.send | {message}')
        
        # Get current available tools
        available_tools = get_available_tools()
        
        response = self._call_wrapper(
            self._model.message,
            message,
            role='user',
            file_contents=file_contents,
            use_tools=True,
            available_tools=available_tools,
        )

        input_tokens = response.get('input_tokens', 0)
        output_tokens = response.get('output_tokens', 0)
        round_count = 1

        loop_result = self._agent_loop(
            response, file_contents or {}, input_tokens, output_tokens, round_count
        )

        return SendResult(
            is_finish=loop_result.is_finish,
            file_contents=loop_result.file_contents,
            input_tokens=loop_result.input_tokens,
            output_tokens=loop_result.output_tokens,
            round_count=loop_result.round_count,
        )

    def load_skill(self, skill_name: str) -> SkillLoadResult:
        """Load specified skill and inject into system prompt."""
        from server.router import _execute_tool
        from server import ToolContext
        from config import get_config
        
        cfg = get_config()
        ctx = ToolContext(cfg=cfg, input_func=input)
        result = _execute_tool('get_skill', {'skill_name': skill_name}, ctx)
        
        # result is a ToolResult object
        skill_text = result.text
        has_file_contents = bool(result.file_contents)
        
        if has_file_contents:
            self._model.inject_skill(skill_name, skill_text)
            log(f'momoka.load_skill | Injected: {skill_name}')
            return SkillLoadResult(success=True, message=skill_text)
        else:
            return SkillLoadResult(success=False, message=skill_text)

    def finish_task(self):
        """Clear all injected skills after task completion."""
        self._model.clear_skills()

    def _init_mcp_client(self):
        """Initialize MCP client"""
        # Ensure MCP logs are suppressed (in case main.py settings were overridden)
        import logging
        logging.getLogger('mcp').setLevel(logging.WARNING)
        
        # Check if MCP SDK is installed
        try:
            import mcp  # noqa: F401
        except ImportError:
            log('MCP: SDK not installed, skipping initialization')
            if self._user:
                self._user.user_log(
                    'MCP SDK not installed. '
                    'Run: \npip install mcp\nto enable MCP connections',
                    role='WARN'
                )
            return

        # Load configuration
        from server.servers.mcp.config_loader import load_mcp_configs
        configs = load_mcp_configs()

        if not configs:
            log('MCP: No MCP servers configured')
            return

        # Create manager and initialize
        from server.servers.mcp.mcp_client import MCPClientManager
        from server.servers.mcp import set_mcp_manager
        from server.servers import get_all_tool_names, invalidate_tool_cache

        # Get builtin tool names before MCP initialization
        builtin_tools = set(get_all_tool_names())

        manager = MCPClientManager()
        
        # Set user reference for logging
        if self._user:
            manager.set_user(self._user)

        try:
            successful = manager.sync_initialize(configs, builtin_tools)

            if successful:
                log(f'MCP: Successfully initialized {len(successful)} server(s): {", ".join(successful)}')
                # Set global manager
                set_mcp_manager(manager)
                # Invalidate tool name cache and rebuild immediately
                invalidate_tool_cache()
                # Force rebuild cache now (instead of waiting for first dispatch_tool call)
                from server.servers import _build_tool_cache
                _build_tool_cache()
                # Verify tools were registered
                from server.servers import get_all_tool_names
                mcp_tools = [n for n in get_all_tool_names() if 'test_server' in n]
                log(f'MCP: Registered MCP tools after cache rebuild: {mcp_tools}')
            else:
                log('MCP: All servers failed to connect')
                if self._user:
                    self._user.user_log('All MCP servers failed to connect', role='WARN')
        except Exception as e:
            log(f'MCP: Initialization failed: {e}')
            if self._user:
                self._user.user_log(f'MCP initialization failed: {e}', role='WARN')

    def _load_preset_conversations(self):
        """Load preset conversations from file."""
        preset_file = os.path.join(os.path.dirname(__file__), 'prompt', 'preset_convs.md')
        try:
            with open(preset_file, 'r', encoding='utf-8') as f:
                preset_convs = json.load(f)
            self._model._ctx.insert_preset_conversations(preset_convs)
        except (FileNotFoundError, json.JSONDecodeError) as e:
            log(f'momoka._load_preset_conversations | Failed to load preset conversations: {e}')

    def repair_history(self) -> int:
        """Repair orphaned tool_calls messages in history."""
        return self._model.repair_history()

    def _check_interrupt(self) -> bool:
        """Check if there's a pending interrupt request, print hint and return True if so."""
        # call_wrapper might be a bound method of CLIUser.call_wrapper,
        # access its pending_interrupt attribute via __self__
        owner = getattr(self._call_wrapper, '__self__', None)
        if owner is not None and getattr(owner, 'pending_interrupt', False):
            return True
        return False

    # ── Agent Loop ─────────────────────────────────────────────────────────

    def _agent_loop(self, response: dict, file_contents: dict,
                    input_tokens: int, output_tokens: int,
                    round_count: int) -> AgentLoopResult:
        """Execute tool call loop until finish or model returns plain text (waiting for user input)."""
        while True:
            text_content: str = response['content']
            tool_calls: list = response['tool_calls']
            # ── Case A: Has tool calls ─────────────────────────────────
            if tool_calls:
                if text_content:
                    if self._user:
                        self._user.user_log(text_content, role='BOT')

                is_finish, file_contents = execute_tool_calls(self._model, tool_calls, user=self._user)
                if is_finish:
                    log('work DONE')
                    return AgentLoopResult(
                        is_finish=True,
                        file_contents=file_contents,
                        input_tokens=input_tokens,
                        output_tokens=output_tokens,
                        round_count=round_count
                    )

                # Tool execution completed this round, check for pending interrupt requests
                if self._check_interrupt():
                    return AgentLoopResult(
                        is_finish=False,
                        file_contents=file_contents,
                        input_tokens=input_tokens,
                        output_tokens=output_tokens,
                        round_count=round_count
                    )

                # Get latest available tools (browser state may have changed)
                available_tools = get_available_tools()

                response = self._call_wrapper(
                    self._model.resume,
                    use_tools=True,
                    available_tools=available_tools
                )
                input_tokens += response.get('input_tokens', 0)
                output_tokens += response.get('output_tokens', 0)
                round_count += 1
                continue

            # ── Case B: Plain text, return control to user ───────────────
            if text_content:
                if self._user:
                    self._user.user_log(text_content, role='BOT')
            return AgentLoopResult(
                is_finish=False,
                file_contents=file_contents,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                round_count=round_count
            )
