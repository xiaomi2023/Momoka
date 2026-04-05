# Momoka Server (BETA)

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
  - [2. calculator.py - Implement Tool Handler](#2-calculatorpy---implement-tool-handler)
  - [3. __init__.py - Register Module](#3-__init__py---register-module)

## Overview

Momoka Server is the way Momoka interacts with external data sources and tools. By customizing Momoka Server and utilizing tool services, context management, and other features, you can enable Momoka to connect and interact with external services.

## Momoka Server Module Structure

Each Momoka Server module follows the following directory structure:

```
server/servers/<name>/
├── __init__.py      # Module registration
├── <name>.py        # Tool handler
└── tooldef.py       # Tool definitions (JSON Schema)
```

## Core Components

### ToolResult

Data class representing tool execution results:

- `text`: str — Text content returned to the model
- `file_contents`: dict[str, str] | None — Processed data information {file_key: content}
- `is_finish`: bool — Whether to end the task (default is False)
- `log_msg`: str | list[tuple[str, str]] | None — Log message provided to the user
- `log_role`: str | None — Log type

### ToolContext

Read-only context object passed to all tool handlers:

- `cfg`: dict — Configuration dictionary
- `input_func`: Callable | None — Input function

### ServerRegistration

Data class used to register Momoka Server modules:

- `name`: str — Module name
- `tool_definitions`: list[dict] — List of tool definitions (JSON Schema)
- `handler`: Callable — Handler function with signature `(str, dict, ToolContext) -> ToolResult`
- `condition`: Callable[[], bool] | one — Availability check function

### Momoka Server Registration API

Can be imported from `server.servers`:

- `register_server(reg: ServerRegistration)` — Register a Server module
- `get_registered_servers() -> dict[str, ServerRegistration]` — Get all registered Servers
- `get_server(name: str) -> ServerRegistration | None` — Get a specific Server by name
- `get_available_tools() -> list[dict]` — Get all available tool definitions
- `dispatch_tool(name: str, args: dict, ctx: ToolContext) -> ToolResult | None` — Dispatch tool calls to the corresponding Server
- `clear_registrations()` — Clear all registrations

## Advanced Features

### Conditional Tool Availability

Through the `condition` parameter of `ServerRegistration`, you can specify a function that returns `bool` to control tool availability. When `condition` returns `False`, all tools of that Momoka Server will not appear in the list returned by `get_available_tools()`, making them unavailable for Momoka to call.

### Context Folding

To reduce context window usage, Momoka supports automatic folding of historical data content. Each time a file is read, the `file_contents` field of `ToolResult` records the filename and content. When the same file is read multiple times or after a task round is completed, file contents in the context are replaced with placeholders, except for the most recent one.

## Example

The following is an example of a custom Momoka Server, demonstrating how to create a simple calculator tool:

### Directory Structure

```
server/servers/calculator/
├── __init__.py      # Module registration
├── calculator.py    # Tool handler implementation
└── tooldef.py       # Tool definitions (JSON Schema)
```

### 1. tooldef.py - Define Tools

```python
"""Calculator tool definitions"""

TOOL_DEFINITIONS = [
    {
        'type': 'function',
        'function': {
            'name': 'calculator',
            'description': 'Perform basic mathematical operations (addition, subtraction, multiplication, division)',
            'parameters': {
                'type': 'object',
                'properties': {
                    'operation': {
                        'type': 'string',
                        'enum': ['add', 'subtract', 'multiply', 'divide'],
                        'description': 'Operation type: add, subtract, multiply, divide'
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
    """Check if calculator tool is available (always available)"""
    return True
```

### 2. calculator.py - Implement Tool Handler

```python
"""Calculator tool handler"""

from server import ToolResult, ToolContext


def calculator(args: dict, ctx: ToolContext) -> ToolResult:
    """
    Execute calculator operation
    
    Args:
        args: Dictionary containing operation, a, b
        ctx: Tool context
    
    Returns:
        ToolResult: Operation result
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
                    return ToolResult(text='Error: Divisor cannot be zero')
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
Provides basic mathematical operation functionality
"""

from __future__ import annotations

from server import ToolResult
from server.servers import ServerRegistration, register_server
from server.servers.calculator.tooldef import TOOL_DEFINITIONS, is_available
from server.servers.calculator import calculator as handler


def _handle(name: str, args: dict, ctx) -> ToolResult:
    """Dispatch tool calls to specific handlers"""
    match name:
        case 'calculator':
            return handler.calculator(args, ctx)
        case _:
            return ToolResult(text=f'Unknown tool: {name}')


# Auto-register module
register_server(ServerRegistration(
    name='calculator',
    tool_definitions=TOOL_DEFINITIONS,
    handler=_handle,
    condition=is_available,
))
```

After creating the above files, Momoka will automatically register and use this Momoka Server.

```
User: Calculate 123 plus 456 for me

→ Momoka calls calculator({"operation": "add", "a": 123, "b": 456})
→ Returns: 123 + 456 = 579
```
