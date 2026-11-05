"""Compatibility launcher for the shopping app."""

from shopping_app import ShoppingBackend, run_interactive_app

__all__ = ["ShoppingBackend", "run_interactive_app"]


if __name__ == "__main__":
    run_interactive_app()
