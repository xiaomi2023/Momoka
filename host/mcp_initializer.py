"""
host/mcp_initializer.py —— MCP 客户端初始化。

负责 MCP SDK 检查、配置加载、客户端初始化和工具注册。
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from logger import log

if TYPE_CHECKING:
    from user.user import BaseUser


class MCPInitializer:
    """MCP 客户端初始化器，负责 MCP 服务器的连接和工具注册。"""

    def __init__(self, user: BaseUser | None = None) -> None:
        self._user = user

    def initialize(self) -> None:
        """初始化 MCP 客户端，加载配置并连接服务器。"""
        # Ensure MCP logs are suppressed
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
                    role='WARN',
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
