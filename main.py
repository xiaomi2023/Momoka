"""Momoka - AI Agent Entry Point.

Supports multiple interface modes:
1. CLI mode (default): Interactive terminal interface
2. Headless mode: Headless interface for pipe/file communication
3. Telegram Bot: Telegram messaging interface
4. Lark/Feishu Bot: Lark messaging interface
5. Discord Bot: Discord messaging interface
6. Slack Bot: Slack messaging interface

Usage:
    # CLI mode
    python main.py

    # Headless mode (stdio)
    python main.py --headless stdio

    # Headless mode (file I/O)
    python main.py --headless file --input input.txt --output output.txt

    # Telegram Bot
    python main.py --interface telegram

    # Lark/Feishu Bot
    python main.py --interface lark

    # Discord Bot
    python main.py --interface discord

    # Slack Bot
    python main.py --interface slack
"""

import argparse
import logging
import sys

from config import get_config, initialize_working_config
from host.momoka import Momoka
from logger import log


# Suppress MCP SDK INFO logs
logging.getLogger('mcp').setLevel(logging.WARNING)
logging.getLogger('httpx').setLevel(logging.WARNING)
logging.getLogger('httpcore').setLevel(logging.WARNING)


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description='Momoka - AI Agent with multiple interfaces',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py                           # CLI mode
  python main.py --interface cli           # CLI mode (explicit)
  python main.py --interface telegram      # Telegram Bot
  python main.py --interface lark          # Lark/Feishu Bot
  python main.py --interface discord       # Discord Bot
  python main.py --interface slack         # Slack Bot
  python main.py --headless stdio          # Headless mode with stdio
  python main.py --headless file \\
           --input input.txt \\
           --output output.txt             # File I/O mode
        """
    )

    parser.add_argument(
        '--interface',
        choices=['cli', 'telegram', 'lark', 'discord', 'slack'],
        default=None,
        help='Interface type to use (overrides config.json)'
    )

    parser.add_argument(
        '--headless',
        choices=['stdio', 'file'],
        default=None,
        help='Run in headless mode: stdio (standard input/output) or file (file I/O)'
    )

    parser.add_argument(
        '--input',
        default='input.txt',
        help='Input file path for file mode (default: input.txt)'
    )

    parser.add_argument(
        '--output',
        default='output.txt',
        help='Output file path for file mode (default: output.txt)'
    )

    return parser.parse_args()


def main():
    """Program entry point."""
    # 初始化运行时配置（确保每次启动从默认工作目录开始）
    initialize_working_config()

    args = parse_args()
    
    # 导入并设置当前接口类型
    from user import set_current_interface

    # Select user interface based on mode
    if args.headless == 'stdio':
        from user.headless import StdioHeadlessUser
        ui = StdioHeadlessUser()
        set_current_interface('headless')
    elif args.headless == 'file':
        from user.headless import FileHeadlessUser
        ui = FileHeadlessUser(
            input_file=args.input,
            output_file=args.output
        )
        set_current_interface('headless')
    else:
        # 确定接口类型: 命令行参数 > 配置文件
        interface = args.interface
        if interface is None:
            cfg = get_config()
            interface = cfg.get('interface', 'cli')
        
        # 设置当前接口类型
        set_current_interface(interface)

        if interface == 'lark':
            from user.lark_bot import LarkBotUser
            cfg = get_config()
            lark_cfg = cfg.get('lark', {})
            app_id = lark_cfg.get('app_id', '')
            app_secret = lark_cfg.get('app_secret', '')
            if not app_id or not app_secret:
                print("Error: Please configure lark.app_id and lark.app_secret")
                sys.exit(1)
            ui = LarkBotUser(
                app_id=app_id,
                app_secret=app_secret
            )
            log('interface | lark bot (WebSocket mode)')

        elif interface == 'discord':
            from user.discord_bot import DiscordBotUser
            cfg = get_config()
            discord_cfg = cfg.get('discord', {})
            token = discord_cfg.get('token', '')
            if not token:
                print("Error: Please configure discord.token")
                sys.exit(1)
            ui = DiscordBotUser(
                token=token,
                allowed_users=discord_cfg.get('allowed_users', []),
                proxy=discord_cfg.get('proxy', None)
            )
            log('interface | discord bot')

        else:
            # Default CLI mode
            from user.cli import CLIUser
            ui = CLIUser()
            log('interface | cli')

    agent = Momoka(user=ui, call_wrapper=ui.call_wrapper if hasattr(ui, 'call_wrapper') else None)
    ui.set_agent(agent)

    try:
        ui.run()
    finally:
        # Clean up resources (file mode needs to close file descriptors)
        if hasattr(ui, 'close'):
            ui.close()


if __name__ == '__main__':
    main()
