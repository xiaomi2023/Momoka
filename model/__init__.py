"""Model package — LLM API communication and context management."""

from model.model import Model, chat
from model.context import Context

__all__ = ['Model', 'Context', 'chat']
