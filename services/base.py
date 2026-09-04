"""Classe-base dos processadores de mesclagem."""

from __future__ import annotations

from pathlib import Path
from typing import Callable, Protocol


ProgressCb = Callable[[int, str], None]


class Merger(Protocol):
    category: str

    def validate_content(self, paths: list[Path]) -> None: ...

    def merge(self, paths: list[Path], output: Path, progress: ProgressCb) -> Path: ...


class BaseMerger:
    category = ""

    def validate_content(self, paths: list[Path]) -> None:
        return None

    def merge(self, paths: list[Path], output: Path, progress: ProgressCb) -> Path:
        raise NotImplementedError
