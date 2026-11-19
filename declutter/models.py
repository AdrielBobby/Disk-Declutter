"""Shared data model for scan results."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Optional

# Item kinds
FILE = "file"
APP = "app"
CACHE = "cache"
DUPLICATE = "duplicate"

# Risk levels
LOW = "low"
MEDIUM = "medium"
HIGH = "high"


@dataclass
class Item:
    """One candidate the user might want to clear."""

    kind: str                       # FILE | APP | CACHE | DUPLICATE
    name: str
    path: str                       # file/folder path, or install location for apps
    size_bytes: int = 0
    last_used: Optional[float] = None   # unix timestamp, best estimate
    last_used_source: str = "unknown"   # atime | mtime | prefetch | registry | unknown
    reason: str = ""
    confidence: float = 0.0         # 0..1 that this is safe to clear
    risk: str = MEDIUM
    deletable: bool = True          # False for apps (uninstall manually) / protected paths
    uninstall_cmd: Optional[str] = None
    ai_verdict: Optional[str] = None
    ai_reason: Optional[str] = None
    extra: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ScanResult:
    items: list[Item] = field(default_factory=list)
    usage_tree: Optional[dict] = None   # folder-size tree for the breakdown view
    scanned_at: float = 0.0
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "items": [i.to_dict() for i in self.items],
            "usage_tree": self.usage_tree,
            "scanned_at": self.scanned_at,
            "errors": self.errors,
        }
