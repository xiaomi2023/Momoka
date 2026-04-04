"""Momoka - AI Agent 程序入口。

支持两种运行模式：
1. CLI 模式（默认）：交互式终端界面
2. Headless 模式：无头接口，适合管道/文件通信

使用方式：
    # CLI 模式
    python main.py

    # Headless 模式（标准输入输出）
    python main.py --headless stdio

    # Headless 模式（文件读写）
    python main.py --headless file --input input.txt --output output.txt
"""

import argparse
import sys

from host.momoka import Momoka


def parse_args():
    """解析命令行参数。"""
    parser = argparse.ArgumentParser(
        description='Momoka - AI Agent',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python main.py                           # CLI 模式
  python main.py --headless stdio          # 标准输入输出无头模式
  python main.py --headless file \\
           --input input.txt \\
           --output output.txt             # 文件读写模式
        """
    )

    parser.add_argument(
        '--headless',
        choices=['stdio', 'file'],
        default=None,
        help='运行无头模式：stdio（标准输入输出）或 file（文件读写）'
    )

    parser.add_argument(
        '--input',
        default='input.txt',
        help='文件模式下的输入文件路径（默认：input.txt）'
    )

    parser.add_argument(
        '--output',
        default='output.txt',
        help='文件模式下的输出文件路径（默认：output.txt）'
    )

    return parser.parse_args()


def main():
    """程序入口。"""
    args = parse_args()

    # 根据模式选择用户接口
    if args.headless == 'stdio':
        from user.headless import StdioHeadlessUser
        ui = StdioHeadlessUser()
    elif args.headless == 'file':
        from user.headless import FileHeadlessUser
        ui = FileHeadlessUser(
            input_file=args.input,
            output_file=args.output
        )
    else:
        # 默认 CLI 模式
        from user.cli import CLIUser
        ui = CLIUser()

    agent = Momoka(user=ui, call_wrapper=ui.call_wrapper if hasattr(ui, 'call_wrapper') else None)
    ui.set_agent(agent)

    try:
        ui.run()
    finally:
        # 清理资源（文件模式需要关闭文件描述符）
        if hasattr(ui, 'close'):
            ui.close()


if __name__ == '__main__':
    main()
