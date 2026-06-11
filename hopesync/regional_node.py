"""Regional Health Node.

A jurisdictionally isolated processing cluster. It holds the anonymized medical
records for its region, ingests normalized data from the Hospital Edge Layer,
and continuously recomputes the ranked candidate set whenever data changes.

Storage is in-memory for the prototype, but the boundaries (no PII here, all
actions audited, RBAC enforced) match the architecture.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .audit import AuditLog
from .auth import Permission, Principal, authorize
from .matching import rank_matches
from .schema import DonorRecord, MatchCandidate, MedicalRecord


@dataclass
class RegionalNode:
    region_id: str
    audit: AuditLog
    patients: dict[str, MedicalRecord] = field(default_factory=dict)
    donors: dict[str, DonorRecord] = field(default_factory=dict)
    # Continuously maintained ranked candidate set, keyed by patient token.
    _match_cache: dict[str, list[MatchCandidate]] = field(default_factory=dict)

    # -- ingestion -------------------------------------------------------
    def ingest_patient(self, principal: Principal, record: MedicalRecord) -> None:
        authorize(principal, Permission.REGISTER_PATIENT)
        self.patients[record.subject_token] = record
        self.audit.record(
            actor=principal.user_id,
            action="patient.ingest",
            details={"region": self.region_id, "subject_token": record.subject_token},
        )
        self._recompute_for_patient(record.subject_token)

    def ingest_donor(self, principal: Principal, record: DonorRecord) -> None:
        authorize(principal, Permission.REGISTER_DONOR)
        self.donors[record.subject_token] = record
        self.audit.record(
            actor=principal.user_id,
            action="donor.ingest",
            details={"region": self.region_id, "subject_token": record.subject_token},
        )
        # A new donor can change matches for every patient: incremental refresh.
        self._recompute_all()

    # -- continuous matching --------------------------------------------
    def _recompute_for_patient(self, patient_token: str) -> None:
        patient = self.patients.get(patient_token)
        if patient is None:
            self._match_cache.pop(patient_token, None)
            return
        self._match_cache[patient_token] = rank_matches(patient, list(self.donors.values()))

    def _recompute_all(self) -> None:
        for token in self.patients:
            self._recompute_for_patient(token)

    # -- queries ---------------------------------------------------------
    def matches_for(self, principal: Principal, patient_token: str) -> list[MatchCandidate]:
        authorize(principal, Permission.VIEW_MATCHES)
        self.audit.record(
            actor=principal.user_id,
            action="matches.view",
            details={"region": self.region_id, "subject_token": patient_token},
        )
        return list(self._match_cache.get(patient_token, []))
