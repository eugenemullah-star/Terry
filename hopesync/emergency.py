"""Emergency Scan Protocol.

When an authorized clinician activates an emergency scan for a patient, the
system elevates priority and runs an immediate (region-wide here) search,
bypassing normal batching delays - but never bypassing hard medical/legal
constraints. Results are time-bound: they expire unless confirmed within a
defined window. Every scan and confirmation is audited.
"""

from __future__ import annotations

import secrets
import time
from dataclasses import dataclass, field

from .auth import Permission, Principal, authorize
from .matching import rank_matches
from .regional_node import RegionalNode
from .schema import MatchCandidate

DEFAULT_TTL_SECONDS = 900.0  # 15 minutes


class EmergencyError(Exception):
    pass


@dataclass
class EmergencyScanResult:
    scan_id: str
    patient_token: str
    candidates: list[MatchCandidate]
    created_at: float
    ttl_seconds: float
    confirmed: bool = False

    def expires_at(self) -> float:
        return self.created_at + self.ttl_seconds

    def is_expired(self, now: float | None = None) -> bool:
        now = time.time() if now is None else now
        return now > self.expires_at()


@dataclass
class EmergencyCoordinator:
    node: RegionalNode
    ttl_seconds: float = DEFAULT_TTL_SECONDS
    _results: dict[str, EmergencyScanResult] = field(default_factory=dict)

    def scan(self, principal: Principal, patient_token: str) -> EmergencyScanResult:
        authorize(principal, Permission.TRIGGER_EMERGENCY)
        patient = self.node.patients.get(patient_token)
        if patient is None:
            raise EmergencyError(f"unknown patient token {patient_token}")

        # Priority elevation: immediate recompute, no batching, larger result set.
        candidates = rank_matches(patient, list(self.node.donors.values()), limit=25)
        result = EmergencyScanResult(
            scan_id="scan_" + secrets.token_hex(6),
            patient_token=patient_token,
            candidates=candidates,
            created_at=time.time(),
            ttl_seconds=self.ttl_seconds,
        )
        self._results[result.scan_id] = result
        self.node.audit.record(
            actor=principal.user_id,
            action="emergency.scan",
            details={
                "scan_id": result.scan_id,
                "subject_token": patient_token,
                "candidate_count": str(len(candidates)),
            },
        )
        return result

    def confirm(self, principal: Principal, scan_id: str) -> EmergencyScanResult:
        authorize(principal, Permission.APPROVE_MATCH)
        result = self._results.get(scan_id)
        if result is None:
            raise EmergencyError(f"unknown scan {scan_id}")
        if result.is_expired():
            self.node.audit.record(
                actor=principal.user_id,
                action="emergency.confirm.expired",
                details={"scan_id": scan_id},
            )
            raise EmergencyError("emergency scan result has expired")
        result.confirmed = True
        self.node.audit.record(
            actor=principal.user_id,
            action="emergency.confirm",
            details={"scan_id": scan_id},
        )
        return result

    def get(self, scan_id: str) -> EmergencyScanResult | None:
        return self._results.get(scan_id)
