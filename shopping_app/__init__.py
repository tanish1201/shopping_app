"""Shopping app backend and interactive terminal entry point."""

from .backend import ShoppingBackend
from .cli import run_interactive_app

__all__ = ["ShoppingBackend", "run_interactive_app"]
