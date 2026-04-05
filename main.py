"""Momoka - AI Agent Entry Point.

Supports two running modes:
1. CLI mode (default): Interactive terminal interface
2. Headless mode: Headless interface for pipe/file communication

Usage:
    # CLI mode
    python main.py

    # Headless mode (stdio)
    python main.py --headless stdio

    # Headless mode (file I/O)
    python main.py --headless file --input input.txt --output output.txt
"""

import argparse
import sys

from host.momoka import Momoka


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description='Momoka',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py                           # CLI mode
  python main.py --headless stdio          # Headless mode with stdio
  python main.py --headless file \\
           --input input.txt \\
           --output output.txt             # File I/O mode
        """
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

    # Select user interface based on mode
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
        # Default CLI mode
        from user.cli import CLIUser
        ui = CLIUser()

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
