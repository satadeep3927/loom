"""Loom package main entry point.

Enables running loom as a module: python -m loom
"""

from .cli.cli import cli

if __name__ == "__main__":
    cli()
