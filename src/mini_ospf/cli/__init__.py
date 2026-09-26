"""
CLI module for Mini-OSPF.
"""

__all__ = ["main"]


def main() -> None:
    from mini_ospf.cli.main import main as _main

    _main()
