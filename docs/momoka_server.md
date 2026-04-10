# Momoka Server (Beta)

### Table of Contents

- [Overview](#overview)
- [Momoka Server Module Structure](#momoka-server-module-structure)
- [Core Components](#core-components)
  - [ToolResult](#toolresult)
  - [ToolContext](#toolcontext)
  - [ServerRegistration](#serverregistration)
  - [Momoka Server Registration API](#momoka-server-registration-api)
- [Advanced Features](#advanced-features)
  - [Conditional Tool Availability](#conditional-tool-availability)
  - [Context Folding](#context-folding)
- [Example](#example)
  - [Directory Structure](#directory-structure)
  - [1. tooldef.py - Define Tools](#1-tooldefpy---define-tools)
  - [2. calculator.py - Implement Tool Handlers](#2-calculatorpy---implement-tool-handlers)
  - [3. __init__.py - Register Module](#3-__init__py---register-module)

## Overview

Momoka Server is the way Momoka interacts with external data sources and tools. By creating custom Momoka Servers and leveraging features like tool services and context management, you can enable Momoka to connect and interact with external services.

## Module Structure

Momoka Server modules are placed in `/server/servers`. Each module should contain an `__init__.py` file to register fields like Tool Definitions, Handlers, etc.

Momoka provides the Tool Definitions to the model, enabling it to call them as needed. After the model makes a tool call, Momoka processes it using the corresponding Handler and can return execution results to the model/user.

## Core Components

### ToolResult

A data class representing the execution result of a tool:

- `text`: str — Text content returned to the model
- `file_contents`: dict[str, str] | None — Processed file information ({file_key: content})
- `is_finish`: bool — Whether to end the task (default: False)
- `log_msg`: str | list[tuple[str, str]] | None — Log message for the user
- `log_role`: str | None — Log role/type

### ToolContext

A read-only context object passed to all tool handlers:

- `cfg`: dict — Configuration dictionary
- `input_func`: Callable | None — Input function

### ServerRegistration

A data class for registering Momoka Server modules:

- `name`: str — Module name
- `tool_definitions`: list[dict] — List of tool definitions (JSON Schema)
- `handler`: Callable | None — Handler function with signature `(str, dict, ToolContext) -> ToolResult` (optional, mutually exclusive with `handlers`)
- `handlers`: dict[str, Callable] | None — Dictionary mapping tool names to handler functions with signature `(dict, ToolContext) -> ToolResult` (recommended, mutually exclusive with `handler`)
- `condition`: Callable[[], bool] | None — Availability check function

### Momoka Server Registration API

Importable from `server.servers`:

- `register_server(reg: ServerRegistration)` — Register a Server module
- `get_registered_servers() -> dict[str, ServerRegistration]` — Get all registered Servers
- `get_server(name: str) -> ServerRegistration | None` — Get a specific Server by name
- `get_available_tools() -> list[dict]` — Get all available tool definitions
- `dispatch_tool(name: str, args: dict, ctx: ToolContext) -> ToolResult | None` — Dispatch a tool call to the corresponding Server
- `clear_registrations()` — Clear all registrations

## Registration Methods

### Method 1: Using handlers Dictionary (Recommended)

Provide a mapping of tool names to handler functions:

```python
from server.servers import ServerRegistration, register_server
from server.servers.my_module.tooldef import TOOL_DEFINITIONS
from server.servers.my_module import my_module as handler

register_server(ServerRegistration(
    name='my_module',
    tool_definitions=TOOL_DEFINITIONS,
    handlers={
        'my_tool': handler.my_tool,
        'another_tool': handler.another_tool,
    },
))
```

Handler function signature: `func(args: dict, ctx: ToolContext) -> ToolResult`

### Method 2: Using Custom Handler Function

If you need more complex dispatch logic, you can create a custom handler function:

```python
from server import ToolResult, UnknownToolError
from server.servers import ServerRegistration, register_server
from server.servers.my_module.tooldef import TOOL_DEFINITIONS
from server.servers.my_module import my_module as handler

def _handle(name: str, args: dict, ctx) -> ToolResult:
    """Dispatch tool calls to specific handlers."""
    match name:
        case 'my_tool':
            return handler.my_tool(args, ctx)
        case 'another_tool':
            return handler.another_tool(args, ctx)
        case _:
            raise UnknownToolError(name)  # Unified exception, will be converted to "Unknown Tool"

register_server(ServerRegistration(
    name='my_module',
    tool_definitions=TOOL_DEFINITIONS,
    handler=_handle,
))
```

## Advanced Features

### Conditional Tool Availability

Using the `condition` parameter of `ServerRegistration`, you can specify a function that returns a `bool` to control tool availability. When `condition` returns `False`, all tools from that Momoka Server will not appear in the list returned by `get_available_tools()`, preventing Momoka from calling them.

### Context Folding

To reduce context window usage, Momoka supports automatic folding of historical data content. Each time a file is read, the `file_contents` field of `ToolResult` records the filename and content. When the same file is read multiple times or after a task round completes, the file content in the context will be replaced with a placeholder, keeping only the most recent content.

## Example

Here's an example of a custom Momoka Server, demonstrating how to create a simple calculator tool:

### Directory Structure

```
server/servers/calculator/
├── __init__.py      # Module registration
├── calculator.py    # Tool handler implementation
└── tooldef.py       # Tool definition (JSON Schema)
```

### 1. tooldef.py - Define Tools

```python
"""Calculator tool definitions"""

TOOL_DEFINITIONS = [
    {
        'type': 'function',
        'function': {
            'name': 'calculator',
            'description': 'Perform basic mathematical operations (add, subtract, multiply, divide)',
            'parameters': {
                'type': 'object',
                'properties': {
                    'operation': {
                        'type': 'string',
                        'enum': ['add', 'subtract', 'multiply', 'divide'],
                        'description': 'Operation type: add, subtract, multiply, or divide'
                    },
                    'a': {
                        'type': 'number',
                        'description': 'First number'
                    },
                    'b': {
                        'type': 'number',
                        'description': 'Second number'
                    }
                },
                'required': ['operation', 'a', 'b']
            }
        }
    }
]


def is_available() -> bool:
    """Check if the calculator tool is available (always available)"""
    return True
```

### 2. calculator.py - Implement Tool Handlers

```python
"""Calculator tool handler"""

from __future__ import annotations

from server import ToolResult, ToolContext


def calculator(args: dict, ctx: ToolContext) -> ToolResult:
    """
    Execute calculator operation

    Args:
        args: Dictionary containing operation, a, and b
        ctx: Tool context

    Returns:
        ToolResult: Calculation result
    """
    operation = args.get('operation')
    a = args.get('a')
    b = args.get('b')

    try:
        match operation:
            case 'add':
                result = a + b
                op_symbol = '+'
            case 'subtract':
                result = a - b
                op_symbol = '-'
            case 'multiply':
                result = a * b
                op_symbol = '*'
            case 'divide':
                if b == 0:
                    return ToolResult(text='Error: Division by zero is not allowed')
                result = a / b
                op_symbol = '/'
            case _:
                return ToolResult(text=f'Unknown operation type: {operation}')

        # Build result text
        result_text = f'{a} {op_symbol} {b} = {result}'

        return ToolResult(
            text=result_text,
            log_msg=f'🧮 Calculator: {result_text}',
            log_role='TOOL'
        )

    except Exception as e:
        return ToolResult(text=f'Calculation error: {str(e)}')
```

### 3. __init__.py - Register Module

```python
"""
calculator Server module
Provides basic mathematical operations
"""

from __future__ import annotations

from server.servers import ServerRegistration, register_server
from server.servers.calculator.tooldef import TOOL_DEFINITIONS, is_available
from server.servers.calculator import calculator as handler


register_server(ServerRegistration(
    name='calculator',
    tool_definitions=TOOL_DEFINITIONS,
    handlers={
        'calculator': handler,
    },
    condition=is_available,
))
```

After creating the files above, Momoka can use this Momoka Server.

```
User: Help me calculate 123 plus 456

→ Momoka calls calculator({"operation": "add", "a": 123, "b": 456})
→ Returns: 123 + 456 = 579
```
