"""CLI package — CLI user interaction implementations (interactive terminal only)."""

from user.cli.cli import CLIUser
from user.cli.util import multiline_input, handle_slash, SLASH_HELP
from user.cli.selector import CliSelectorAdapter, SelectorCallbacks
from user.cli.interactions import CliInteractionAdapter


__all__ = [
    'CLIUser',
    'multiline_input',
    'handle_slash',
    'SLASH_HELP',
    'CliSelectorAdapter',
    'SelectorCallbacks',
    'CliInteractionAdapter',
]
