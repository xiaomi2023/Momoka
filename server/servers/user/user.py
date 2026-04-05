"""
server/servers/user/user.py —— User interaction tool handlers.

Covers: ask_user, set_todolist, ask_option

架构说明：
- Server 层仅依赖 user/interactions.py 的纯业务逻辑类
- 通过 CLI 适配器（CliInteractionAdapter、CliSelectorAdapter）提供渲染能力
- 实现了分层解耦，方便未来支持其他 UI（如 GUI、Web）
"""

from __future__ import annotations

from server import ToolResult, ToolContext


def ask_user(args: dict, ctx: ToolContext) -> ToolResult:
    """Ask the user a question and wait for a reply."""
    from rich.console import Console
    from user.interactions import AskUser
    from user.cli.interactions import CliInteractionAdapter

    question = args.get('question', '')
    
    # 创建业务逻辑实例
    ask_user_instance = AskUser(question)
    
    # 创建 CLI 适配器并提供输入函数
    console = Console(highlight=False)
    adapter = CliInteractionAdapter(console)
    callbacks = adapter.make_ask_user_callbacks()
    
    # 覆写 get_input 以使用 ctx.input_func
    original_get_input = callbacks.get_input
    callbacks.get_input = lambda prompt: ctx.input_func(prompt) if ctx.input_func else original_get_input(prompt)

    # 运行交互
    reply = ask_user_instance.run(callbacks)
    text = f'Reply: {reply}' if reply else '(NULL)'

    return ToolResult(
        text=text,
        log_msg=None,  # 问题已通过 callbacks.render_question 打印，不需要重复日志
        log_role='QUESTION',
    )


def set_todolist(args: dict, ctx: ToolContext) -> ToolResult:
    """Display a todo_list to the user."""
    from rich.console import Console
    from user.interactions import TodoList
    from user.cli.interactions import CliInteractionAdapter

    tasks = args.get('tasks', [])
    
    # 创建业务逻辑实例
    todolist_instance = TodoList(tasks)
    
    # 创建 CLI 适配器
    console = Console(highlight=False)
    adapter = CliInteractionAdapter(console)
    callbacks = adapter.make_todolist_callbacks()

    # 运行交互，获取纯文本版本（用于日志）
    display_text = todolist_instance.run(callbacks)

    return ToolResult(
        text=f'Showed todo list:\n{display_text}',
        log_msg=None,  # 已经通过 callbacks 渲染到终端，不需要再输出日志
        log_role='TOOL',
    )


def ask_option(args: dict, ctx: ToolContext) -> ToolResult:
    """Display options to the user and let them select one or more.

    委托给 user/selector.py 处理所有业务逻辑，
    通过 CLI 层的 CliSelectorAdapter 提供终端渲染回调。
    """
    from user.selector import OptionSelector
    from user.cli.selector import CliSelectorAdapter
    from rich.console import Console

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

    # 创建选择器和 CLI 适配器
    selector = OptionSelector(normalized_options, question, allow_multiple)
    console = Console(highlight=False)
    adapter = CliSelectorAdapter(console)
    callbacks = adapter.make_callbacks()

    # 运行选择器
    result_text = selector.run(callbacks, input_func=ctx.input_func)

    return ToolResult(
        text=result_text,
        log_msg=f'{question}->{result_text}',
        log_role='QUESTION',
    )


# ── Availability check functions (always available) ──────────────────────────

def is_available() -> bool:
    """User tools are always available."""
    return True
