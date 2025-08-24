"""Smart Rails keyword-based CRUD system."""

from .processors import ListProcessor, TaskProcessor
from .router import KeywordRouter

__all__ = ["KeywordRouter", "ListProcessor", "TaskProcessor"]
