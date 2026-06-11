"""Append-only, cryptographically chained audit log.

Each entry stores the hash of the previous entry, forming a tamper-evident
chain (a minimal blockchain-style ledger). Any modification or deletion of a
historical record breaks the chain and is detectable via :meth:`AuditLog.verify`.

This mirrors the Governance and Audit Layer: it only observes, it cannot alter
operational behaviour, and it is append-only.
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import asdict, dataclass

GENESIS_HASH = "0" * 64


@dataclass(frozen=True)
class AuditEntry:
    index: int
    timestamp: float
    actor: str
    action: str
    details: dict[str, str]
    prev_hash: str
    entry_hash: str = ""

    def compute_hash(self) -> str:
        payload = {
            "index": self.index,
            "timestamp": self.timestamp,
            "actor": self.actor,
            "action": self.action,
            "details": self.details,
            "prev_hash": self.prev_hash,
        }
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


class AuditLog:
    """In-memory append-only audit ledger."""

    def __init__(self) -> None:
        self._entries: list[AuditEntry] = []

    def record(self, actor: str, action: str, details: dict[str, str] | None = None) -> AuditEntry:
        details = details or {}
        prev_hash = self._entries[-1].entry_hash if self._entries else GENESIS_HASH
        draft = AuditEntry(
            index=len(self._entries),
            timestamp=time.time(),
            actor=actor,
            action=action,
            details=details,
            prev_hash=prev_hash,
        )
        sealed = AuditEntry(**{**asdict(draft), "entry_hash": draft.compute_hash()})
        self._entries.append(sealed)
        return sealed

    def verify(self) -> bool:
        """Return True if the entire chain is intact and untampered."""
        prev_hash = GENESIS_HASH
        for entry in self._entries:
            if entry.prev_hash != prev_hash:
                return False
            if entry.compute_hash() != entry.entry_hash:
                return False
            prev_hash = entry.entry_hash
        return True

    @property
    def entries(self) -> list[AuditEntry]:
        return list(self._entries)

    def __len__(self) -> int:
        return len(self._entries)
