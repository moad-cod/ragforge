"""Chunking package.

Public chunker metadata lives in app.services.chunkers.registry.
This package initializer intentionally avoids importing chunker modules so
registry imports stay lightweight and do not load optional ML dependencies.
"""

__all__ = []
