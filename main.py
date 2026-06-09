"""Momoka - AI Agent Entry Point.

Supports multiple interface modes:
1. CLI mode (default): Interactive terminal interface
2. Headless mode: Headless interface for pipe/file communication
3. Lark/Feishu Bot: Lark messaging interface
4. Discord Bot: Discord messaging interface
5. QQ Bot: QQ messaging interface

Usage:
    # CLI mode
    python main.py

    # CLI mode with custom config
    python main.py --config my_config.json

    # Headless mode (stdio)
    python main.py --headless stdio

    # Headless mode (file I/O)
    python main.py --headless file --input input.txt --output output.txt

    # Lark/Feishu Bot
    python main.py --interface lark

    # Discord Bot
    python main.py --interface discord

    # QQ Bot
    python main.py --interface qq
"""

import nest_asyncio
nest_asyncio.apply()
import argparse
import logging
import os
import sys

from config import get_config, initialize_working_config, set_config_file
from host.momoka import Momoka
from logger import log


# Suppress MCP SDK INFO logs
logging.getLogger('mcp').setLevel(logging.WARNING)
logging.getLogger('httpx').setLevel(logging.WARNING)
logging.getLogger('httpcore').setLevel(logging.WARNING)


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description='Momoka - An personal AI assistant',
        formatter_class=argparse.RawDescriptionHelpFormatter)

    parser.add_argument(
        '--config',
        default=None,
        help='Path to a custom configuration file (overrides config.json)'
    )

    parser.add_argument(
        '--interface',
        choices=['cli', 'lark', 'discord', 'qq'],
        default=None,
        help='Interface type to use (overrides config.json)'
    )

    parser.add_argument(
        '--init',
        action='store_true',
        help='Initialize work_dir to the current directory'
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
    args = parse_args()

    # 如果指定了 --config，优先使用自定义配置文件
    if args.config:
        try:
            set_config_file(args.config)
            log(f'config | 使用自定义配置文件: {args.config}')
        except FileNotFoundError as e:
            print(f'Error: {e}')
            sys.exit(1)

    # --init 参数：将 config.json 的 work_dir 设置为当前目录，然后继续启动
    if args.init:
        import json as _json
        _base = os.path.dirname(os.path.abspath(__file__))
        _cfg_debug = os.path.join(_base, 'config_debug.json')
        _cfg_default = os.path.join(_base, 'config.json')
        cfg_path = args.config if args.config else (
            _cfg_debug if os.path.exists(_cfg_debug) else _cfg_default
        )
        cfg_path = os.path.abspath(cfg_path)
        with open(cfg_path, 'r', encoding='utf-8') as _f:
            _cfg = _json.load(_f)
        _cfg['work_dir'] = os.getcwd()
        with open(cfg_path, 'w', encoding='utf-8') as _f:
            _json.dump(_cfg, _f, ensure_ascii=False, indent=2)
        log(f'config | --init: work_dir 已设置为当前目录并继续启动: {os.getcwd()}')

    # 初始化运行时配置（确保每次启动从默认工作目录开始）
    initialize_working_config()

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
            from user.bot.lark.lark_bot import LarkBotUser
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
            from user.bot.discord.discord_bot import DiscordBotUser
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

        elif interface == 'qq':
            from user.bot.qq.qq_bot import QQBotUser
            cfg = get_config()
            qq_cfg = cfg.get('qq', {})
            app_id = qq_cfg.get('app_id', '')
            app_secret = qq_cfg.get('app_secret', '')
            sandbox = qq_cfg.get('sandbox', False)
            if not app_id or not app_secret:
                print("Error: Please configure qq.app_id and qq.app_secret")
                sys.exit(1)
            ui = QQBotUser(
                app_id=app_id,
                app_secret=app_secret,
                sandbox=sandbox
            )
            log('interface | qq bot (WebSocket mode)')

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
