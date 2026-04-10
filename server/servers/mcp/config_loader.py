"""
server/servers/mcp/config_loader.py —— MCP configuration loader and validator.

Loads MCP server configuration from config.json and performs validation.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Literal

from config import get_config
from logger import log


@dataclass
class MCPServerConfig:
    """Single MCP Server configuration"""
    name: str
    transport: Literal["stdio", "sse", "http"]
    command: str | None = None
    args: list[str] = field(default_factory=list)
    url: str | None = None
    env: dict[str, str] = field(default_factory=dict)
    description: str = ""
    enabled: bool = True
    prefix: str = ""


def validate_mcp_config(config: dict) -> list[str]:
    """Validate MCP configuration legality.

    Checks:
    - Whether transport protocol is valid (stdio/sse/http)
    - Whether required fields exist
    - Whether local paths are valid in stdio mode (if args contain paths)

    Args:
        config: Configuration dict for single MCP server

    Returns:
        Error message list, empty means validation passed
    """
    errors = []
    transport = config.get('transport')

    if transport not in ('stdio', 'sse', 'http'):
        errors.append(f"Unsupported transport type: {transport}")
        return errors

    if transport == 'stdio':
        if not config.get('command'):
            errors.append("stdio transport requires command field")
        if 'args' not in config:
            errors.append("stdio transport requires args field")

        # Validate local paths in args (if any)
        args = config.get('args', [])
        for arg in args:
            # Check if it's an absolute path (Windows or Unix style)
            if (os.path.isabs(arg) or
                (len(arg) > 2 and arg[1] == ':' and arg[2] in ('/', '\\'))):
                if not os.path.exists(arg):
                    errors.append(f"Path does not exist: {arg}")
                # Note: args can be files (scripts) or directories, both are valid

    if transport in ('sse', 'http'):
        if not config.get('url'):
            errors.append(f"{transport} transport requires url field")
        else:
            # Simple URL format validation
            url = config.get('url', '')
            if not url.startswith(('http://', 'https://')):
                errors.append(f"Invalid URL format, requires http:// or https:// prefix: {url}")

    return errors


def load_mcp_configs() -> list[MCPServerConfig]:
    """Load MCP server configurations from config.json

    Returns:
        List of valid MCP server configurations
    """
    cfg = get_config()
    mcp_config = cfg.get("mcp_servers", {})

    configs = []
    for name, config in mcp_config.items():
        if not config.get("enabled", True):
            log(f'MCP: Skipping disabled server: {name}')
            continue

        errors = validate_mcp_config(config)
        if errors:
            log(f'MCP configuration validation failed ({name}): {"; ".join(errors)}')
            continue

        configs.append(MCPServerConfig(**config))

    return configs
