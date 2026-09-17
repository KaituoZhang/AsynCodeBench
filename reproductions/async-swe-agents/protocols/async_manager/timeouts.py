"""Per-conversation timeout override; never leak manager caps to worker threads."""

from contextvars import ContextVar

manager_timeout = ContextVar("async_manager_conversation_timeout", default=None)
