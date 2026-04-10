# MCP Server Integration Guide (BETA)

### Table of Contents

- [Overview](#overview)
- [Prerequisites](#prerequisites)
- [Configuration](#configuration)
  - [Configuration File Location](#configuration-file-location)
  - [Basic Structure](#basic-structure)
  - [Transport Protocols](#transport-protocols)
- [Configuration Parameters](#configuration-parameters)
- [Examples](#examples)
  - [stdio Transport (Local Process)](#stdio-transport-local-process)
  - [sse/http Transport (Remote Server)](#ssehttp-transport-remote-server)

## Overview

MCP (Model Context Protocol) is an open standard for connecting AI agents to external data sources and tools. Momoka supports MCP servers, enabling seamless integration with third-party services such as GitHub, Slack, databases, and more.

By configuring MCP servers, Momoka can automatically invoke tools provided by these servers during conversations.

## Prerequisites

Before configuring MCP servers, ensure that the MCP SDK is installed:

```bash
pip install mcp
```

## Configuration

### Configuration File Location

MCP server configurations should be added under the `mcp_servers` key in `config.json`. Each server is identified by a unique name.

### Basic Structure

```json
{
  "api_key": "sk-XXX",
  "base_url": "https://api.XXX.com",
  "model": "gpt-4o",
  "work_dir": "C:\\Users\\...",
  "mcp_servers": {
    "server_name": {
      "name": "server_name",
      "transport": "stdio",
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-example"],
      "env": {},
      "description": "Example MCP server",
      "enabled": true,
      "prefix": "example"
    }
  }
}
```

### Transport Protocols

Momoka supports three MCP transport protocols:

| Protocol | Description | Required Fields |
|----------|-------------|-----------------|
| `stdio` | Local process communication via standard I/O | `command`, `args` |
| `sse` | Server-Sent Events (remote server) | `url` |
| `http` | HTTP-based communication (remote server) | `url` |

## Configuration Parameters

| Parameter     | Type           | Required       | Description                                                         |
|---------------|----------------|----------------|---------------------------------------------------------------------|
| `name`        | string         | Yes            | Server identifier name                                              |
| `transport`   | string         | Yes            | Transport protocol: `stdio`, `sse`, or `http`                       |
| `command`     | string         | Yes (stdio)    | Command to start the server process (e.g., `npx`, `python`, `node`) |
| `args`        | list[str]      | Yes (stdio)    | Command-line arguments for starting the server                      |
| `url`         | string         | Yes (sse/http) | Server URL (must start with `http://` or `https://`)                |
| `env`         | dict[str, str] | No             | Environment variables to pass to the server process                 |
| `description` | string         | No             | Server description for documentation purposes                       |
| `enabled`     | bool           | No             | Whether to enable this server (default: `true`)                     |
| `prefix`      | string         | No             | Tool name prefix to avoid naming conflicts (default: server name)   |

## Examples

### stdio Transport (Local Process)

#### GitHub MCP Server

Connect to GitHub for repository management, Issues, PRs, and file operations:

```json
{
  "mcp_servers": {
    "github": {
      "name": "github",
      "transport": "stdio",
      "command": "npx",
      "args": [
        "-y",
        "@modelcontextprotocol/server-github"
      ],
      "env": {
        "GITHUB_PERSONAL_ACCESS_TOKEN": "your_github_token"
      },
      "description": "GitHub MCP Server - Repository management, Issues, PRs, file operations",
      "enabled": true,
      "prefix": "github"
    }
  }
}
```

#### Custom Python Script

Run a custom Python-based MCP server:

```json
{
  "mcp_servers": {
    "custom_tool": {
      "name": "custom_tool",
      "transport": "stdio",
      "command": "python",
      "args": [
        "C:\\Users\\YourName\\my_mcp_server.py"
      ],
      "description": "Custom Python MCP Server",
      "enabled": true,
      "prefix": "custom"
    }
  }
}
```

### sse/http Transport (Remote Server)

Connect to a remote MCP server via HTTP:

```json
{
  "mcp_servers": {
    "remote_server": {
      "name": "remote_server",
      "transport": "sse",
      "url": "https://your-mcp-server.com/mcp",
      "description": "Remote MCP server connected via SSE",
      "enabled": true,
      "prefix": "remote"
    }
  }
}
```

## More Information
For more information about MCP, visit: [Model Context Protocol](https://modelcontextprotocol.io/docs/).
