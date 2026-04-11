"""
server/servers/user/user.py —— User interaction tool handlers.

Covers: ask_user, set_todolist, ask_option

架构说明：
- Server 层根据 user.interface_type 选择对应的适配器
- CLI 使用 CliInteractionAdapter、CliSelectorAdapter
- Lark 使用 LarkAskUserAdapter、LarkTodoListAdapter、LarkSelectorAdapter
- Discord 使用 DiscordAskUserAdapter、DiscordTodoListAdapter、DiscordSelectorAdapter
- QQ 使用 QQAskUserAdapter、QQTodolistAdapter、QQSelectorAdapter
- Headless 使用 HeadlessAskUserAdapter、HeadlessTodoListAdapter、HeadlessSelectorAdapter
"""

from __future__ import annotations

from server.types import ToolResult, ToolContext


def ask_user(args: dict, ctx: ToolContext) -> ToolResult:
    """Ask the user a question and wait for a reply."""
    question = args.get('question', '')

    # 根据用户接口类型选择适配器
    user = ctx.user if ctx else None
    interface_type = getattr(user, 'interface_type', 'cli') if user else 'cli'

    if interface_type == 'lark':
        # 飞书模式
        from user.lark_bot.interactions import LarkAskUserAdapter
        from user.interactions import AskUser

        ask_user_instance = AskUser(question)
        adapter = LarkAskUserAdapter(user)
        callbacks = adapter.make_callbacks()
        reply = ask_user_instance.run(callbacks)
        text = f'Reply: {reply}' if reply else '(NULL)'

    elif interface_type == 'discord':
        # Discord 模式
        from user.discord_bot.interactions import DiscordAskUserAdapter
        from user.interactions import AskUser

        ask_user_instance = AskUser(question)
        adapter = DiscordAskUserAdapter(user)
        callbacks = adapter.make_callbacks()
        reply = ask_user_instance.run(callbacks)
        text = f'Reply: {reply}' if reply else '(NULL)'

    elif interface_type == 'qq':
        # QQ 模式
        from user.qq_bot.interactions import QQAskUserAdapter
        from user.interactions import AskUser

        ask_user_instance = AskUser(question)
        adapter = QQAskUserAdapter(user)
        callbacks = adapter.make_callbacks()
        reply = ask_user_instance.run(callbacks)
        text = f'Reply: {reply}' if reply else '(NULL)'

    elif interface_type == 'headless':
        # 无头模式
        from user.headless.interactions import HeadlessAskUserAdapter
        from user.interactions import AskUser

        ask_user_instance = AskUser(question)
        adapter = HeadlessAskUserAdapter(user)
        callbacks = adapter.make_callbacks()
        reply = ask_user_instance.run(callbacks)
        text = f'Reply: {reply}' if reply else '(NULL)'

    else:
        # CLI 模式（默认）
        from rich.console import Console
        from user.interactions import AskUser
        from user.cli.interactions import CliInteractionAdapter

        ask_user_instance = AskUser(question)
        console = Console(highlight=False)
        adapter = CliInteractionAdapter(console)
        callbacks = adapter.make_ask_user_callbacks()

        reply = ask_user_instance.run(callbacks)
        text = f'Reply: {reply}' if reply else '(NULL)'

    return ToolResult(
        text=text,
        log_msg=None,  # 问题已通过 callbacks.render_question 打印，不需要重复日志
        log_role='QUESTION',
    )


def set_todolist(args: dict, ctx: ToolContext) -> ToolResult:
    """Display a todo_list to the user."""
    tasks = args.get('tasks', [])

    # 根据用户接口类型选择适配器
    user = ctx.user if ctx else None
    interface_type = getattr(user, 'interface_type', 'cli') if user else 'cli'

    if interface_type == 'lark':
        # 飞书模式
        from user.lark_bot.interactions import LarkTodoListAdapter
        from user.interactions import TodoList

        todolist_instance = TodoList(tasks)
        adapter = LarkTodoListAdapter(user)
        callbacks = adapter.make_callbacks()
        display_text = todolist_instance.run(callbacks)

    elif interface_type == 'discord':
        # Discord 模式
        from user.discord_bot.interactions import DiscordTodoListAdapter
        from user.interactions import TodoList

        todolist_instance = TodoList(tasks)
        adapter = DiscordTodoListAdapter(user)
        callbacks = adapter.make_callbacks()
        display_text = todolist_instance.run(callbacks)

    elif interface_type == 'qq':
        # QQ 模式
        from user.qq_bot.interactions import QQTodolistAdapter
        from user.interactions import TodoList

        todolist_instance = TodoList(tasks)
        adapter = QQTodolistAdapter(user)
        callbacks = adapter.make_callbacks()
        display_text = todolist_instance.run(callbacks)

    elif interface_type == 'headless':
        # 无头模式
        from user.headless.interactions import HeadlessTodoListAdapter
        from user.interactions import TodoList

        todolist_instance = TodoList(tasks)
        adapter = HeadlessTodoListAdapter(user)
        callbacks = adapter.make_callbacks()
        display_text = todolist_instance.run(callbacks)

    else:
        # CLI 模式（默认）
        from rich.console import Console
        from user.interactions import TodoList
        from user.cli.interactions import CliInteractionAdapter

        todolist_instance = TodoList(tasks)
        console = Console(highlight=False)
        adapter = CliInteractionAdapter(console)
        callbacks = adapter.make_todolist_callbacks()
        display_text = todolist_instance.run(callbacks)

    return ToolResult(
        text=f'Showed todo list:\n{display_text}',
        log_msg=None,  # 已经通过 callbacks 渲染到终端，不需要再输出日志
        log_role='TOOL',
    )


def ask_option(args: dict, ctx: ToolContext) -> ToolResult:
    """Display options to the user and let them select one or more."""
    from user.selector import OptionSelector

    question = args.get('question', 'Choose:')
    options = args.get('options', [])
    allow_multiple = args.get('allow_multiple', False)

    if not options:
        return ToolResult(
            text='<Error: No options were provided>',
            log_role='ERROR',
        )

    # 标准化选项数据
    normalized_options = [
        {
            'label': opt.get('label', f'Option{i+1}'),
            'description': opt.get('description', ''),
        }
        for i, opt in enumerate(options)
    ]

    # 根据用户接口类型选择适配器
    user = ctx.user if ctx else None
    interface_type = getattr(user, 'interface_type', 'cli') if user else 'cli'

    if interface_type == 'lark':
        # 飞书模式
        from user.lark_bot.interactions import LarkSelectorAdapter

        selector = OptionSelector(normalized_options, question, allow_multiple)
        adapter = LarkSelectorAdapter(user)
        result_text = adapter.run_selector(selector)

    elif interface_type == 'discord':
        # Discord 模式
        from user.discord_bot.interactions import DiscordSelectorAdapter

        selector = OptionSelector(normalized_options, question, allow_multiple)
        adapter = DiscordSelectorAdapter(user)
        result_text = adapter.run_selector(selector)

    elif interface_type == 'qq':
        # QQ 模式
        from user.qq_bot.interactions import QQSelectorAdapter

        selector = OptionSelector(normalized_options, question, allow_multiple)
        adapter = QQSelectorAdapter(user)
        result_text = adapter.run_selector(selector)

    elif interface_type == 'headless':
        # 无头模式
        from user.headless.interactions import HeadlessSelectorAdapter

        selector = OptionSelector(normalized_options, question, allow_multiple)
        adapter = HeadlessSelectorAdapter(user)
        result_text = adapter.run_selector(selector)

    else:
        # CLI 模式（默认）
        from user.selector import OptionSelector
        from user.cli.selector import CliSelectorAdapter
        from rich.console import Console

        selector = OptionSelector(normalized_options, question, allow_multiple)
        console = Console(highlight=False)
        adapter = CliSelectorAdapter(console)
        callbacks = adapter.make_callbacks()
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
