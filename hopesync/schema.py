"""Unified medical schema.

The schema enforces the core Hope Sync principle: Identity Data and Medical
Data are different types and live in different stores. The matching layer only
ever consumes :class:`MedicalRecord` / :class:`DonorRecord` objects, which carry
an opaque ``subject_token`` rather than any personally identifiable information.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field

# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------


class BloodType(enum.StrEnum):
    O_NEG = "O-"
    O_POS = "O+"
    A_NEG = "A-"
    A_POS = "A+"
    B_NEG = "B-"
    B_POS = "B+"
    AB_NEG = "AB-"
    AB_POS = "AB+"


class OrganType(enum.StrEnum):
    KIDNEY = "kidney"
    LIVER = "liver"
    HEART = "heart"
    LUNG = "lung"
    PANCREAS = "pancreas"


# Maximum cold ischemia time (hours) an organ remains viable for transplant.
ORGAN_MAX_ISCHEMIA_HOURS: dict[OrganType, float] = {
    OrganType.HEART: 4.0,
    OrganType.LUNG: 6.0,
    OrganType.LIVER: 12.0,
    OrganType.PANCREAS: 12.0,
    OrganType.KIDNEY: 24.0,
}


class Role(enum.StrEnum):
    CLINICIAN = "clinician"
    COORDINATOR = "transplant_coordinator"
    HOSPITAL_ADMIN = "hospital_admin"
    REGIONAL_AUTHORITY = "regional_authority"
    AUDITOR = "auditor"
    ENGINEER = "engineer"


# ---------------------------------------------------------------------------
# Identity data (PII) - stored ONLY in the Identity Vault.
# ---------------------------------------------------------------------------


@dataclass
class IdentityData:
    """Personally identifiable information. Never passed to matching engines."""

    full_name: str
    national_id: str
    phone: str | None = None
    email: str | None = None


# ---------------------------------------------------------------------------
# Medical data (anonymized) - the only data the matching layer sees.
# ---------------------------------------------------------------------------


@dataclass
class GeoLocation:
    latitude: float
    longitude: float
    hospital_id: str


@dataclass
class MedicalRecord:
    """Anonymized patient record consumed by the matching engine."""

    subject_token: str
    blood_type: BloodType
    needed_organ: OrganType
    hla_antigens: frozenset[str]
    # 0..100, higher means more medically urgent (deterioration model output).
    urgency_score: float
    location: GeoLocation
    institution_readiness: float = 1.0  # 0..1


@dataclass
class DonorRecord:
    """Anonymized donor record consumed by the matching engine."""

    subject_token: str
    blood_type: BloodType
    available_organ: OrganType
    hla_antigens: frozenset[str]
    location: GeoLocation
    eligible: bool = True
    # Hours remaining before the organ is no longer viable.
    organ_viability_hours: float = 24.0


@dataclass
class MatchCandidate:
    """A ranked candidate produced by the matching engine."""

    patient_token: str
    donor_token: str
    organ: OrganType
    score: float
    confidence: float
    components: dict[str, float] = field(default_factory=dict)
    constraints: list[str] = field(default_factory=list)
