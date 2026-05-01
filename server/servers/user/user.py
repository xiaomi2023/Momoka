"""
server/servers/user/user.py —— User interaction tool handlers.

Covers: ask_user, set_todolist, ask_option

架构说明：
- Server 层根据 user.interface_type 自动选择对应的适配器
- 每种 interface_type 对应一个适配器模块
"""

from __future__ import annotations

from server.types import ToolResult, ToolContext


def _get_ask_user_adapter(user):
    """根据 interface_type 获取对应的 AskUser 适配器。"""
    interface_type = getattr(user, 'interface_type', 'cli') if user else 'cli'

    if interface_type == 'lark':
        from user.bot.lark.interactions import LarkAskUserAdapter
        return LarkAskUserAdapter(user)
    elif interface_type == 'discord':
        from user.bot.discord.interactions import DiscordAskUserAdapter
        return DiscordAskUserAdapter(user)
    elif interface_type == 'qq':
        from user.bot.qq.interactions import QQAskUserAdapter
        return QQAskUserAdapter(user)
    elif interface_type == 'headless':
        from user.headless.interactions import HeadlessAskUserAdapter
        return HeadlessAskUserAdapter(user)
    else:
        from rich.console import Console
        from user.cli.interactions import CliInteractionAdapter
        return CliInteractionAdapter(Console(highlight=False))


def _get_todolist_adapter(user):
    """根据 interface_type 获取对应的 TodoList 适配器。"""
    interface_type = getattr(user, 'interface_type', 'cli') if user else 'cli'

    if interface_type == 'lark':
        from user.bot.lark.interactions import LarkTodoListAdapter
        return LarkTodoListAdapter(user)
    elif interface_type == 'discord':
        from user.bot.discord.interactions import DiscordTodoListAdapter
        return DiscordTodoListAdapter(user)
    elif interface_type == 'qq':
        from user.bot.qq.interactions import QQTodolistAdapter
        return QQTodolistAdapter(user)
    elif interface_type == 'headless':
        from user.headless.interactions import HeadlessTodoListAdapter
        return HeadlessTodoListAdapter(user)
    else:
        from rich.console import Console
        from user.cli.interactions import CliInteractionAdapter
        return CliInteractionAdapter(Console(highlight=False))


def _get_selector_adapter(user):
    """根据 interface_type 获取对应的 Selector 适配器。"""
    interface_type = getattr(user, 'interface_type', 'cli') if user else 'cli'

    if interface_type == 'lark':
        from user.bot.lark.interactions import LarkSelectorAdapter
        return LarkSelectorAdapter(user)
    elif interface_type == 'discord':
        from user.bot.discord.interactions import DiscordSelectorAdapter
        return DiscordSelectorAdapter(user)
    elif interface_type == 'qq':
        from user.bot.qq.interactions import QQSelectorAdapter
        return QQSelectorAdapter(user)
    elif interface_type == 'headless':
        from user.headless.interactions import HeadlessSelectorAdapter
        return HeadlessSelectorAdapter(user)
    else:
        from rich.console import Console
        from user.cli.selector import CliSelectorAdapter
        return CliSelectorAdapter(Console(highlight=False))


def ask_user(args: dict, ctx: ToolContext) -> ToolResult:
    """Ask the user a question and wait for a reply."""
    from user.interactions import AskUser

    question = args.get('question', '')
    user = ctx.user if ctx else None
    adapter = _get_ask_user_adapter(user)

    if hasattr(adapter, 'make_ask_user_callbacks'):
        callbacks = adapter.make_ask_user_callbacks()
    elif hasattr(adapter, 'make_callbacks'):
        callbacks = adapter.make_callbacks()
    else:
        callbacks = adapter.make_callbacks() if hasattr(adapter, 'make_callbacks') else None

    ask_user_instance = AskUser(question)
    reply = ask_user_instance.run(callbacks) if callbacks else '(NULL)'
    text = f'Reply: {reply}' if reply else '(NULL)'

    return ToolResult(
        text=text,
        log_msg=None,
        log_role='QUESTION',
    )


def set_todolist(args: dict, ctx: ToolContext) -> ToolResult:
    """Display a todo_list to the user."""
    from user.interactions import TodoList

    tasks = args.get('tasks', [])
    user = ctx.user if ctx else None
    adapter = _get_todolist_adapter(user)

    if hasattr(adapter, 'make_todolist_callbacks'):
        callbacks = adapter.make_todolist_callbacks()
    elif hasattr(adapter, 'make_callbacks'):
        callbacks = adapter.make_callbacks()
    else:
        callbacks = None

    todolist_instance = TodoList(tasks)
    display_text = todolist_instance.run(callbacks) if callbacks else '(EMPTY)'

    return ToolResult(
        text=f'Showed todo list:\n{display_text}',
        log_msg=None,
        log_role='TOOL',
    )


def ask_option(args: dict, ctx: ToolContext) -> ToolResult:
    """Display options to the user and let them select one or more."""
    from user.selector import OptionSelector

    question = args.get('question', 'Choose:')
    options = args.get('options', [])
    allow_multiple = args.get('allow_multiple', False)

    if not options:
        return ToolResult(text='<Error: No options were provided>', log_role='ERROR')

    normalized_options = [
        {'label': opt.get('label', f'Option{i+1}'), 'description': opt.get('description', '')}
        for i, opt in enumerate(options)
    ]

    user = ctx.user if ctx else None
    adapter = _get_selector_adapter(user)

    selector = OptionSelector(normalized_options, question, allow_multiple)

    if hasattr(adapter, 'run_selector'):
        result_text = adapter.run_selector(selector)
    else:
        # CLI 模式：使用 callbacks
        callbacks = adapter.make_callbacks() if hasattr(adapter, 'make_callbacks') else None
        result_text = selector.run(callbacks, input_func=ctx.input_func if ctx else None)

    return ToolResult(
        text=result_text,
        log_msg=f'{question} -> {result_text}',
        log_role='QUESTION',
    )


# ── Availability check functions (always available) ──────────────────────────

def is_available() -> bool:
    """User tools are always available."""
    return True
