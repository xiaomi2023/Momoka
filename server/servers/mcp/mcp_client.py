"""
server/servers/mcp/mcp_client.py —— MCP client core implementation.

Uses independent thread to run event loop, completely isolated from Playwright.
Provides thread-safe synchronous call interfaces.
"""

from __future__ import annotations

import asyncio
import sys
import threading
import time
from typing import TYPE_CHECKING

from logger import log
from server import ToolResult

if TYPE_CHECKING:
    from mcp import ClientSession
    from server.servers.mcp.config_loader import MCPServerConfig


class MCPClientManager:
    """MCP client manager, manages multiple MCP Server connections.

    Uses independent thread to run event loop, completely isolated from Playwright.
    """

    def __init__(self):
        self._sessions: dict[str, tuple] = {}  # server_name → (session, cm)
        self._tools: dict[str, str] = {}  # tool_name → server_name mapping
        self._tool_original_names: dict[str, str] = {}  # prefixed_name → original_name mapping
        self._tool_definitions: list[dict] = []  # OpenAI format tool definitions

        # Independent thread event loop
        self._mcp_loop: asyncio.AbstractEventLoop | None = None
        self._mcp_thread: threading.Thread | None = None
        self._loop_ready = threading.Event()
        
        # User reference for logging
        self._user = None

    def set_user(self, user) -> None:
        """Set user reference for logging.
        
        Args:
            user: User instance with user_log method
        """
        self._user = user
    
    def _user_log(self, message: str, role: str = 'MCP') -> None:
        """Output user log if user reference is available.
        
        Args:
            message: Log message
            role: Log role (default: MCP)
        """
        if self._user and hasattr(self._user, 'user_log'):
            self._user.user_log(message, role=role)

    def _ensure_mcp_loop(self):
        """Ensure MCP event loop thread is started"""
        if self._mcp_loop is not None:
            return

        self._mcp_thread = threading.Thread(
            target=self._run_event_loop,
            daemon=True,
            name='MCP-EventLoop'
        )
        self._mcp_thread.start()

        # Wait for event loop to be ready
        if not self._loop_ready.wait(timeout=5.0):
            raise RuntimeError('MCP event loop startup timeout')

    def _run_event_loop(self):
        """Run event loop in independent thread"""
        self._mcp_loop = asyncio.new_event_loop()
        # Note: Python 3.10+ no longer requires set_event_loop(), use self._mcp_loop directly
        self._loop_ready.set()

        try:
            self._mcp_loop.run_forever()
        finally:
            self._mcp_loop.close()
            self._mcp_loop = None

    def _run_async(self, coro, timeout: float = 30.0):
        """Run async coroutine in MCP thread (thread-safe)

        Args:
            coro: Coroutine to execute
            timeout: Timeout in seconds

        Returns:
            Execution result of the coroutine

        Raises:
            TimeoutError: If operation times out
        """
        self._ensure_mcp_loop()

        future = asyncio.run_coroutine_threadsafe(coro, self._mcp_loop)

        try:
            return future.result(timeout=timeout)
        except TimeoutError:
            future.cancel()
            raise TimeoutError(f'MCP operation timed out ({timeout}s)')

    def sync_initialize(self, configs: list[MCPServerConfig],
                        builtin_tools: set[str] | None = None) -> list[str]:
        """
        Synchronously initialize all configured MCP Servers

        Args:
            configs: MCP server configuration list
            builtin_tools: Built-in tool names (for conflict detection)

        Returns:
            List of successfully connected server names
        """
        if builtin_tools is None:
            builtin_tools = set()

        self._user_log(f'Initializing {len(configs)} MCP server(s)...')

        async def _init():
            successful = []
            for config in configs:
                try:
                    await self._connect_server(config)
                    successful.append(config.name)
                    log(f"MCP Server '{config.name}' connected successfully")

                    # Register tools (with prefix), check conflicts immediately
                    prefix = config.prefix or config.name
                    tools = await self._list_tools_for_server(config.name)
                    tool_count = 0
                    for tool in tools:
                        tool_name = f"{prefix}_{tool.name}"

                        # Conflict detection: skip MCP tools that conflict with builtin tools
                        if tool_name in builtin_tools:
                            log(f"MCP: Skipping conflicting tool '{tool_name}' (conflicts with builtin)")
                            continue

                        self._tools[tool_name] = config.name
                        self._tool_original_names[tool_name] = tool.name  # Save original name
                        self._tool_definitions.append(
                            self._to_openai_format(tool_name, tool)
                        )
                        tool_count += 1
                        
                except Exception as e:
                    log(f"MCP Server '{config.name}' connection failed: {e}")
                    self._user_log(f"Failed to connect to MCP server '{config.name}': {e}", role='WARN')

            if successful:
                total_tools = len(self._tools)
                self._user_log(f"MCP initialization complete: {len(successful)} server(s), {total_tools} tool(s) available")
            
            return successful

        return self._run_async(_init(), timeout=60.0)

    async def _connect_server(self, config: MCPServerConfig):
        """Connect to single MCP Server (async)

        Args:
            config: MCP server configuration

        Raises:
            ValueError: If transport protocol is not supported
            Exception: If connection fails
        """
        from mcp import ClientSession
        from mcp.client.stdio import stdio_client, StdioServerParameters
        from mcp.client.sse import sse_client

        if config.transport == "stdio":
            server_params = StdioServerParameters(
                command=config.command,
                args=config.args,
                env=config.env if config.env else None
            )
            cm = stdio_client(server_params)
        elif config.transport in ("sse", "http"):
            cm = sse_client(config.url)
        else:
            raise ValueError(f"Unsupported transport protocol: {config.transport}")

        # Start transport and create session (auto cleanup on failure)
        session = None
        try:
            read_stream, write_stream = await cm.__aenter__()
            session = ClientSession(read_stream, write_stream)
            await session.__aenter__()

            # Initialize session
            await session.initialize()
        except Exception:
            # Clean up created resources
            if session is not None:
                try:
                    await session.__aexit__(*sys.exc_info())
                except Exception:
                    pass  # Ignore cleanup errors
            await cm.__aexit__(*sys.exc_info())
            raise

        # Save session and context manager (for later cleanup)
        self._sessions[config.name] = (session, cm)

    async def _list_tools_for_server(self, server_name: str) -> list:
        """Get tool list for specified server (async)

        Args:
            server_name: Server name

        Returns:
            Tool list
        """
        session, _ = self._sessions[server_name]
        tools_result = await session.list_tools()
        return tools_result.tools

    def _to_openai_format(self, tool_name: str, mcp_tool) -> dict:
        """Convert MCP tool definition to OpenAI Tool format

        Args:
            tool_name: Tool name (with prefix)
            mcp_tool: MCP tool object

        Returns:
            OpenAI format tool definition
        """
        # Handle inputSchema, may be dict or object
        input_schema = getattr(mcp_tool, 'inputSchema', {})
        if input_schema is None:
            input_schema = {"type": "object", "properties": {}}

        return {
            "type": "function",
            "function": {
                "name": tool_name,
                "description": getattr(mcp_tool, 'description', ''),
                "parameters": input_schema
            }
        }

    def get_openai_tool_definitions(self) -> list[dict]:
        """Get all MCP tool definitions in OpenAI format

        Returns:
            OpenAI format tool definition list
        """
        return self._tool_definitions.copy()

    def is_mcp_tool(self, tool_name: str) -> bool:
        """Check if tool is an MCP tool

        Args:
            tool_name: Tool name

        Returns:
            Whether it's an MCP tool
        """
        return tool_name in self._tools

    def get_server_for_tool(self, tool_name: str) -> str | None:
        """Get MCP Server name corresponding to a tool

        Args:
            tool_name: Tool name

        Returns:
            Corresponding server name, or None if not found
        """
        return self._tools.get(tool_name)

    def remove_tool(self, tool_name: str) -> None:
        """Remove specified tool (for handling tool name conflicts).

        Args:
            tool_name: Tool name to remove
        """
        if tool_name in self._tools:
            server_name = self._tools.pop(tool_name)
            # Remove from tool definitions list
            self._tool_definitions = [
                t for t in self._tool_definitions
                if t.get('function', {}).get('name') != tool_name
            ]
            log(f"MCP: Removed tool '{tool_name}' (server: {server_name})")

    def call_tool_sync(self, server_name: str, tool_name: str,
                       arguments: dict, timeout: float = 30.0) -> ToolResult:
        """
        Synchronously call MCP tool (thread-safe, with complete error handling)

        This is the entry point called by the router layer.

        Timeout strategy:
        - Inner layer: asyncio.wait_for() controls single tool execution timeout
        - Outer layer: _run_async() timeout slightly larger than inner (+5s), as safety net
        - Dual timeout ensures no indefinite blocking while allowing time for cleanup

        Args:
            server_name: MCP server name
            tool_name: Tool name
            arguments: Tool arguments
            timeout: Timeout in seconds

        Returns:
            Tool execution result
        """
        self._user_log(f"Call: {tool_name} (server: {server_name})")
        
        async def _call():
            # Inner timeout: control tool execution itself
            return await asyncio.wait_for(
                self._call_tool(server_name, tool_name, arguments),
                timeout=timeout
            )

        try:
            # Outer timeout: slightly larger than inner, allow time for coroutine cancellation and cleanup
            result = self._run_async(_call(), timeout=timeout + 5.0)
            return result
        except TimeoutError:
            return ToolResult(
                text=f"Tool execution timed out ({timeout}s)",
                log_msg=f"MCP tool timeout: {tool_name} (server: {server_name}, timeout: {timeout}s)",
                log_role='WARN'
            )
        except Exception as e:
            return ToolResult(
                text=f"Tool execution failed: {e}",
                log_msg=f"MCP tool error: {tool_name} (server: {server_name}) - {e}",
                log_role='ERROR'
            )

    async def _call_tool(self, server_name: str, tool_name: str,
                         arguments: dict) -> ToolResult:
        """Call tool on specified server (async)

        Args:
            server_name: Server name
            tool_name: Tool name (may include prefix)
            arguments: Tool arguments

        Returns:
            Tool execution result
        """
        from mcp.types import TextContent, ImageContent, EmbeddedResource

        # Get the original tool name (without prefix)
        original_tool_name = self._tool_original_names.get(tool_name, tool_name)

        session, _ = self._sessions[server_name]
        result = await session.call_tool(original_tool_name, arguments)

        # Check error flag
        if getattr(result, 'isError', False):
            text_parts = []
            for content in result.content:
                if isinstance(content, TextContent) and hasattr(content, 'text'):
                    text_parts.append(content.text)
                else:
                    text_parts.append(str(content))

            return ToolResult(
                text='\n'.join(text_parts) if text_parts else str(result),
                log_msg=f"MCP tool error: {tool_name} (server: {server_name})",
                log_role='ERROR'
            )

        # Handle various content types
        text_parts = []
        for content in result.content:
            if isinstance(content, TextContent) and hasattr(content, 'text'):
                text_parts.append(content.text)
            elif isinstance(content, ImageContent):
                text_parts.append(f"[Image: {getattr(content, 'mimeType', 'unknown')}]")
            elif isinstance(content, EmbeddedResource):
                text_parts.append(f"[Resource: {getattr(content, 'uri', 'unknown')}]")
            else:
                text_parts.append(str(content))

        return ToolResult(text='\n'.join(text_parts) if text_parts else str(result))

    def sync_cleanup(self):
        """Synchronously clean up all connections.

        Each Server's cleanup is independently wrapped in try-except,
        ensuring single failure won't interrupt cleanup of other Servers.
        """
        async def _cleanup():
            for name, (session, cm) in list(self._sessions.items()):
                try:
                    # Clean up session first
                    try:
                        await session.__aexit__(None, None, None)
                        log(f"MCP Server '{name}' session closed")
                    except Exception as e:
                        log(f"MCP Server '{name}' session close failed: {e}")

                    # Then clean up context manager (transport)
                    try:
                        await cm.__aexit__(None, None, None)
                        log(f"MCP Server '{name}' transport closed")
                    except Exception as e:
                        log(f"MCP Server '{name}' transport close failed: {e}")
                except Exception as e:
                    log(f"MCP Server '{name}' cleanup exception: {e}")

            self._sessions.clear()
            self._tools.clear()
            self._tool_original_names.clear()
            self._tool_definitions.clear()
            log("MCP: All connections cleaned up")

        if self._mcp_loop is not None and self._mcp_loop.is_running():
            try:
                self._run_async(_cleanup(), timeout=15.0)
            except Exception as e:
                log(f"MCP cleanup error: {e}")
            finally:
                # Ensure event loop is stopped
                self._mcp_loop.call_soon_threadsafe(self._mcp_loop.stop)
                if self._mcp_thread is not None:
                    self._mcp_thread.join(timeout=5.0)
