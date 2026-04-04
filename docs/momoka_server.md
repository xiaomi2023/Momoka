# Momoka Server (BETA)

Momoka Server is the way Momoka interacts with external data sources and tools.
Through tool services, context management, and other features,
it enables Momoka to connect and interact with external services.

---

## Table

- [1. Server Architecture](#1-server-architecture)
- [2. Server Module Structure](#2-server-module-structure)
- [3. Creating Custom Server Modules](#3-creating-custom-server-modules)
  - [Writing Tool Definitions (tooldef.py)](#writing-tool-definitions-tooldefpy)
  - [Writing Tool Handlers (handler.py)](#writing-tool-handlers-handlerpy)
  - [Exporting Module Interface (__init__.py)](#exporting-module-interface-__init__py)
- [4. Registering Custom Servers](#4-registering-custom-servers)
  - [4.1 Registering in tool_registry.py](#41-registering-in-tool_registrypy)
  - [4.2 Adding Routes in router.py](#42-adding-routes-in-routerpy)
- [5. Data Class Descriptions](#5-data-class-descriptions)
  - [5.1 ToolResult](#51-toolresult)
  - [5.2 ToolContext](#52-toolcontext)
- [6. Tool Handler Writing Specifications](#6-tool-handler-writing-specifications)
  - [6.1 Function Signature](#61-function-signature)
- [7. Advanced Features](#7-advanced-features)
  - [7.1 Conditional Availability Tools](#71-conditional-availability-tools)
  - [7.2 File Content Injection and History Folding](#72-file-content-injection-and-history-folding)
  - [7.3 Dynamic Tool Registration](#73-dynamic-tool-registration)

---

## 1. Server Architecture

Momoka's Server layer adopts a tool registration + routing dispatch architecture.

**Core Components:**
- `tool_registry.py`: Tool registration center, collects tool definitions from each module and generates the available tool list
- `router.py`: Tool routing dispatcher, dispatches tool_calls to corresponding handlers, and uniformly handles logging and history
- `servers/<name>/`: Tool module directories.

---

## 2. Server Module Structure

Each Server module is an independent Python package with the following standard structure:

```
server/servers/<name>/
├── __init__.py          # Module export interface
├── handler.py           # Tool handler implementation
└── tooldef.py           # Tool definitions
```

---

## 3. Creating Custom Server Modules

### Writing Tool Definitions (tooldef.py)

`tooldef.py` is used to define the JSON Schema of tools. Momoka uses these definitions to understand the functionality and parameters of tools.

**Basic Template:**

```python
"""
server/servers/weather/tooldef.py — Weather query tool definitions.
"""

from __future__ import annotations

# ── Tool Definitions ─────────────────────────────────────────────────────────

TOOL_DEFINITIONS: list[dict] = [
    {
        'type': 'function',
        'function': {
            'name': 'get_weather',
            'description': 'Query the current weather for a specified city.',
            'parameters': {
                'type': 'object',
                'properties': {
                    # properties...
                },
                'required': ['city'],
            },
        },
    },
]


# ── Availability Check ───────────────────────────────────────────────────────

def is_available() -> bool:
    """Weather tool is always available."""
    return True
```

### Writing Tool Handlers (handler.py)

`handler.py` implements the actual execution logic of tools, receives parameters, and returns `ToolResult`.

**Basic Template:**

```python
"""
server/servers/weather/handler.py — Weather query tool handler.
"""

from __future__ import annotations

import traceback

from logger import log
from server import ToolResult, ToolContext


def get_weather(args: dict, ctx: ToolContext) -> ToolResult:
    """Weather query tool handler.

    Args:
        args: Tool parameters, e.g., {'city': 'Beijing', 'unit': 'celsius'}
        ctx: Execution context, containing configuration and other information

    Returns:
        ToolResult: Execution result
    """
    city = args.get('city', '')
    unit = args.get('unit', 'celsius')
    
    # ── Actual Business Logic ─────────────────────────────
    # Here you can call external APIs, read files, execute commands, etc.
    # Example: Simulating weather data
    temperature = 25 if unit == 'celsius' else 77
    weather_desc = 'Partly Cloudy'
    result_text = f'{city} current weather: {weather_desc}, temperature {temperature}°{unit[0].upper()}'
    # ──────────────────────────────────────────────────────

    return ToolResult(
        text=f'<{city} weather query successful>',
        log_msg=f'Weather Query: {city} → {result_text}',
        log_role='TOOL',
    )
```

### Exporting Module Interface (__init__.py)

`__init__.py` exports the public interface of the module:

```python
"""Weather server package."""

from __future__ import annotations

from server.servers.weather.handler import get_weather
from server.servers.weather.tooldef import TOOL_DEFINITIONS, is_available

__all__ = ['get_weather', 'TOOL_DEFINITIONS', 'is_available']
```

---

## 4. Registering Custom Servers

After creating the module, you need to register it in the tool registry and router before Momoka can call it.

### 4.1 Registering in tool_registry.py

Edit `server/tool_registry.py` and add the module to the `_SERVER_REGISTRATIONS` list:

```python
_SERVER_REGISTRATIONS: list[tuple[str, str, str | None]] = [
    # Existing registrations...
    # ── New: Weather Tool ─────────────────────────────────
    ('server.servers.weather.tooldef', 'TOOL_DEFINITIONS', None),
    # ──────────────────────────────────────────────────────
]
```

**Parameter Description:**
- 1st parameter: Path to the module tool definition (`server.servers.module.tooldef`)
- 2nd parameter: Tool definition variable name (default `TOOL_DEFINITIONS`)
- 3rd parameter: Condition check function name (`None` means always available)

### 4.2 Adding Routes in router.py

Edit `server/router.py` and add routes in the `_execute_tool()` function:

```python
def _execute_tool(name: str, args: dict, ctx: ToolContext,
                  work_model=None) -> ToolResult:
    match name:
        # ── New: Weather Tool ────────────────────────────────
        case 'get_weather':      return weather_handler.get_weather(args, ctx)
        # ───────────────────────────────────────────────────
```

**You also need to import the module at the top of the file:**

```python
# from ... import ...
from server.servers import weather as weather_handler  # ← New
```

---

## 5. Data Class Descriptions

### 5.1 ToolResult

`ToolResult` is the return value of tool execution:

```python
@dataclass
class ToolResult:
    """Tool execution result.

    text:          Text content returned to the model (required)
    file_contents: File content read this time, format {file_key: content} (optional)
    is_finish:     True indicates finish() was called, round terminates (default False)
    log_msg:       Log to output to user; None means no log
                   str                   → Single entry, role determined by log_role
                   list[tuple[str,str]]  → Multiple entries, each as (msg, role)
    log_role:      Role for single log entry, default 'TOOL'
    """
    text: str
    file_contents: dict[str, str] = field(default_factory=dict)
    is_finish: bool = False
    log_msg: str | list[tuple[str, str]] | None = None
    log_role: str = 'TOOL'
```

### 5.2 ToolContext

`ToolContext` is the read-only context during tool execution:

```python
@dataclass
class ToolContext:
    """Read-only context required for tool execution.

    cfg:          Current configuration dictionary
    input_func:   User input function (default input)
    """
    cfg: dict
    input_func: Callable = field(default=input)
```

---

## 6. Tool Handler Writing Specifications

### 6.1 Function Signature

All tool handlers follow a unified signature:

```python
def tool_name(args: dict, ctx: ToolContext) -> ToolResult:
    """Tool description docstring."""
    # Implementation logic
    return ToolResult(text='...')
```

---

## 7. Advanced Features

### 7.1 Conditional Availability Tools

You can use condition check functions to implement tools that are only triggered under specific conditions:

**tooldef.py:**

```python
def is_my_tool_available() -> bool:
    """My tool is only available under specific conditions."""
    try:
        from server.servers.my_module import is_ready
        return is_ready()
    except ImportError:
        return False
```

**tool_registry.py Registration:**

```python
('server.servers.my_tool.tooldef', 'TOOL_DEFINITIONS', 'is_my_tool_available'),
```

Condition functions must return `bool`.

### 7.2 File Content Injection and History Folding

When tools process data sources like files, you can inject content into history through the `file_contents` field to trigger automatic folding, thereby reducing Token consumption:

```python
def read_my_file(args: dict, ctx: ToolContext) -> ToolResult:
    file_path = args.get('file_path', '')
    content = read_file_content(file_path)

    return ToolResult(
        text=f'Opened File: {file_path}\n{content}',
        file_contents={file_path: content},  # ← Triggers history folding
        log_msg=f'Read File: {file_path}',
    )
```

### 7.3 Dynamic Tool Registration

Dynamically register tools at runtime:

```python
from server.tool_registry import register_server_tools

# Dynamic registration
register_server_tools(
    module_path='my_plugin.tools',
    tools_var_name='MY_TOOLS',
    condition_func_name='is_plugin_available',
)
```
