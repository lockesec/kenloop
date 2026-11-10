"""Shared pieces for modules that register commands (the commands seam): the parser
class every subcommand group uses, and the argument types more than one module needs."""
from __future__ import annotations

import argparse

from . import home as H
from .errors import UsageError


class Parser(argparse.ArgumentParser):
    def error(self, message):
        sub = self.prog.removeprefix(H.PROG).strip()   # main() prefixes "ken: "
        raise UsageError(f"{sub + ': ' if sub else ''}{message}")


def count(text: str) -> int:
    """A whole number of at least 1 (a count of items to show or take)."""
    try:
        n = int(text)
    except ValueError:
        raise argparse.ArgumentTypeError(f"{text!r} is not a whole number") from None
    if n < 1:
        raise argparse.ArgumentTypeError(f"{text} must be 1 or more")
    return n
