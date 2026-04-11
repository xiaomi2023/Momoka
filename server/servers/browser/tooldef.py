"""
server/servers/browser/tooldef.py — Browser tool definitions.

Covers: all browse_* tools

Tools are divided into two groups:
  - BROWSER_BASE_TOOLS: basic browser tools (always available)
  - BROWSER_PAGE_TOOLS: browser page interaction tools (available only after the browser is opened)
"""

from __future__ import annotations

from config import get_config

# ── Basic browser tools (always available) ─────────────────────────────────

BROWSER_BASE_TOOLS: list[dict] = [
    {
        'type': 'function',
        'function': {
            'name': 'browse_open',
            'description': 'Open the specified webpage using the Chromium browser.',
            'parameters': {
                'type': 'object',
                'properties': {
                    'url': {'type': 'string', 'description': 'The URL of the webpage to open'},
                },
                'required': ['url'],
            },
        },
    },
    {
        'type': 'function',
        'function': {
            'name': 'browse_search',
            'description': 'Search for keywords using a search engine.',
            'parameters': {
                'type': 'object',
                'properties': {
                    'query': {'type': 'string', 'description': 'The keywords to search for'},
                    'engine': {
                        'type': 'string',
                        'enum': ['google', 'bing', 'baidu', 'duckduckgo'],
                        'description': 'Search engine. Defaults to google. Supports google, bing, baidu, and duckduckgo.',
                        'default': 'google',
                    },
                },
                'required': ['query'],
            },
        },
    },
]

# ── Browser page interaction tools (available only after the browser is opened) ─

BROWSER_PAGE_TOOLS: list[dict] = [
    {
        'type': 'function',
        'function': {
            'name': 'browse_read',
            'description': (
                "Read the content of the current browser page. Supports three modes:\n"
                "  'interactive' — list interactive elements (ID, type, label text, extra info)\n"
                "  'text'        — show the page body text (with Markdown formatting: tables, lists, code blocks, quotes, bold/italic, links)\n"
                "  'all'         — body text + interactive elements (default)\n"
                "Call this after each browser operation to confirm the result."
            ),
            'parameters': {
                'type': 'object',
                'properties': {
                    'char_start': {
                        'type': 'integer',
                        'description': 'Start character position (0-based). Defaults to 0',
                        'default': 0,
                    },
                    'char_end': {
                        'type': 'integer',
                        'description': 'End character position (exclusive). Defaults to 4000',
                        'default': 4000,
                    },
                    'mode': {
                        'type': 'string',
                        'enum': ['all', 'interactive', 'text'],
                        'description': "Reading mode. Defaults to 'all'",
                        'default': 'all',
                    },
                },
                'required': [],
            },
        },
    },
    {
        'type': 'function',
        'function': {
            'name': 'browse_click',
            'description': 'Click the interactive element with the specified ID on the page.',
            'parameters': {
                'type': 'object',
                'properties': {
                    'element_uuid': {
                        'type': 'string',
                        'description': 'Element ID',
                    },
                },
                'required': ['element_uuid'],
            },
        },
    },
    {
        'type': 'function',
        'function': {
            'name': 'browse_fill',
            'description': 'Fill text into the input element (textbox / searchbox / combobox) with the specified ID.',
            'parameters': {
                'type': 'object',
                'properties': {
                    'element_uuid': {
                        'type': 'string',
                        'description': 'Element ID',
                    },
                    'text': {
                        'type': 'string',
                        'description': 'The text content to fill in',
                    },
                },
                'required': ['element_uuid', 'text'],
            },
        },
    },
    {
        'type': 'function',
        'function': {
            'name': 'browse_press',
            'description': 'Send a key press to the element with the specified ID.',
            'parameters': {
                'type': 'object',
                'properties': {
                    'element_uuid': {
                        'type': 'string',
                        'description': 'Element ID',
                    },
                    'key': {
                        'type': 'string',
                        'description': 'Key name, such as Enter, Tab, Escape, ArrowDown, etc.',
                    },
                },
                'required': ['element_uuid', 'key'],
            },
        },
    },
    {
        'type': 'function',
        'function': {
            'name': 'browse_find',
            'description': 'Search for visible elements containing the specified text on the current page, and return the matching element selectors and text snippets.',
            'parameters': {
                'type': 'object',
                'properties': {
                    'text': {'type': 'string', 'description': 'The text to search for'},
                    'max_results': {
                        'type': 'integer',
                        'description': 'Maximum number of results to return. Defaults to 10',
                        'default': 10,
                    },
                },
                'required': ['text'],
            },
        },
    },
    {
        'type': 'function',
        'function': {
            'name': 'browse_pdf',
            'description': 'Export the current browser page as a PDF file.',
            'parameters': {
                'type': 'object',
                'properties': {
                    'save_dir': {
                        'type': 'string',
                        'description': 'Directory to save the PDF. Defaults to the working directory',
                    },
                },
                'required': [],
            },
        },
    },
    {
        'type': 'function',
        'function': {
            'name': 'browse_eval',
            'description': (
                'Execute a JavaScript expression in the current browser page and return the result.\n'
            ),
            'parameters': {
                'type': 'object',
                'properties': {
                    'script': {'type': 'string', 'description': 'The JavaScript expression to execute'},
                },
                'required': ['script'],
            },
        },
    },
    {
        'type': 'function',
        'function': {
            'name': 'browse_wait_for_navigation',
            'description': 'Wait for the current page navigation to complete. Call this when the page is navigating to ensure the page is fully loaded before performing other operations.',
            'parameters': {
                'type': 'object',
                'properties': {
                    'timeout': {
                        'type': 'integer',
                        'description': 'Maximum wait time (seconds)',
                        'default': get_config()['wait'],
                    },
                    'state': {
                        'type': 'string',
                        'enum': ['load', 'domcontentloaded', 'networkidle'],
                        'description': "Loading state to wait for. 'load' waits for the load event, 'domcontentloaded' waits for DOM parsing to complete, 'networkidle' waits for network to be idle",
                        'default': 'networkidle'
                    }
                },
                'required': []
            },
        },
    },
    {
        'type': 'function',
        'function': {
            'name': 'browse_hover',
            'description': 'Hover the mouse over the element with the specified ID to trigger the hover event.',
            'parameters': {
                'type': 'object',
                'properties': {
                    'element_uuid': {
                        'type': 'string',
                        'description': 'Element ID',
                    },
                },
                'required': ['element_uuid'],
            },
        },
    },
    {
        'type': 'function',
        'function': {
            'name': 'browse_select',
            'description': (
                'Select an option in the native <select> dropdown with the specified ID. '
                "The value can be the option's display text (label), value attribute, or numeric index.md (e.g. '0', '1'). "
                'For non-native selects (e.g. custom dropdown components), use browse_click together with browse_hover.'
            ),
            'parameters': {
                'type': 'object',
                'properties': {
                    'element_uuid': {
                        'type': 'string',
                        'description': 'Element ID returned by browse_read',
                    },
                    'value': {
                        'type': 'string',
                        'description': 'The option to select. Can be display text, value attribute, or numeric index.md',
                    },
                },
                'required': ['element_uuid', 'value'],
            },
        },
    },
    {
        'type': 'function',
        'function': {
            'name': 'browse_get_url',
            'description': 'Return the URL and title of the current page.',
            'parameters': {
                'type': 'object',
                'properties': {},
                'required': [],
            },
        },
    },
    {
        'type': 'function',
        'function': {
            'name': 'browse_upload',
            'description': (
                'Upload one or more local files to the file input with the specified ID.\n'
                'Paths must be absolute or relative to the current working directory.'
            ),
            'parameters': {
                'type': 'object',
                'properties': {
                    'element_uuid': {
                        'type': 'string',
                        'description': 'File input element ID',
                    },
                    'file_paths': {
                        'oneOf': [
                            {'type': 'string'},
                            {'type': 'array', 'items': {'type': 'string'}},
                        ],
                        'description': 'Local file paths to upload. Pass a string for a single file, or a list for multiple files',
                    },
                },
                'required': ['element_uuid', 'file_paths'],
            },
        },
    },
    {
        'type': 'function',
        'function': {
            'name': 'browse_download',
            'description': (
                'Click the download link or button with the specified ID, wait for the browser download to complete, '
                'and save the file to the specified directory.\n'
                'Download timeout defaults to 60 seconds.'
            ),
            'parameters': {
                'type': 'object',
                'properties': {
                    'element_uuid': {
                        'type': 'string',
                        'description': 'Download link/button ID returned by browse_read',
                    },
                    'save_dir': {
                        'type': 'string',
                        'description': 'Directory to save the file. Defaults to the current working directory',
                    },
                },
                'required': ['element_uuid'],
            },
        },
    },
    {
        'type': 'function',
        'function': {
            'name': 'browse_scroll',
            'description': 'Scroll the page or the specified element. Supports directions: up / down / left / right. \n'
            "Unless necessary, prioritize adjusting char_start and char_end of browser_read to read more content.",
            'parameters': {
                'type': 'object',
                'properties': {
                    'direction': {
                        'type': 'string',
                        'enum': ['down', 'up', 'left', 'right'],
                        'description': "Scroll direction. Defaults to 'down'",
                        'default': 'down',
                    },
                    'amount': {
                        'type': 'integer',
                        'description': 'Number of pixels to scroll. Defaults to 500',
                        'default': 500,
                    },
                    'element_uuid': {
                        'type': 'string',
                        'description': 'Optional. If provided, scrolls the inner container of that element; otherwise scrolls the entire page',
                    },
                },
                'required': [],
            },
        },
    },
    {
        'type': 'function',
        'function': {
            'name': 'browse_close',
            'description': 'Close the browser.',
            'parameters': {
                'type': 'object',
                'properties': {},
                'required': [],
            },
        },
    },
]


# ── Availability checks ────────────────────────────────────────────────────

def is_browser_base_available() -> bool:
    """Basic browser tools are always available."""
    return True


def is_browser_page_available() -> bool:
    """
    Browser page interaction tools are only available after the browser is opened.
    This function is called by the Host layer to decide whether to include these tools.
    """
    # Lazy import to avoid circular dependencies
    try:
        from server.servers.browser.handler import is_browser_open
        return is_browser_open()
    except ImportError:
        return False


# ── Full tool list (backward compatibility) ────────────────────────────────

ALL_BROWSER_TOOLS: list[dict] = BROWSER_BASE_TOOLS + BROWSER_PAGE_TOOLS


# ── Get available browser tools ────────────────────────────────────────────

def get_browser_tools(browser_open: bool = False) -> list[dict]:
    """Get the list of available browser tools based on the browser state.

    Args:
        browser_open: Whether the browser is already open

    Returns:
        List of available browser tools
    """
    tools = BROWSER_BASE_TOOLS.copy()
    if browser_open:
        tools = tools + BROWSER_PAGE_TOOLS
    return tools
