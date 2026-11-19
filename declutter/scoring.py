"""Rule-based scoring: turn raw scanner items into reasons, confidence and risk."""

from __future__ import annotations

from .models import Item


def score_items(items: list[Item], stale_days: int) -> None:
    """Fill reason/confidence/risk in place. TODO: implement rules per item kind."""
    for _ in items:
        pass
