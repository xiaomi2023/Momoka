"""User package — User interaction interfaces and CLI implementation."""

from user.user import BaseUser
from user.cli import CLIUser
from user.cli_util import multiline_input, handle_slash, SLASH_HELP

__all__ = ['BaseUser', 'CLIUser', 'multiline_input', 'handle_slash', 'SLASH_HELP']
