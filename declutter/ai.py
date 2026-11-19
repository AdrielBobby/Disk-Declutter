"""Optional local-model reasoning via Ollama. Metadata only, never file contents."""

from __future__ import annotations

from .models import Item


def review(items: list[Item], model: str) -> None:
    """Annotate low-confidence items with ai_verdict / ai_reason. TODO: call Ollama."""
    raise NotImplementedError("AI review is not implemented yet")
