"""Core matching engine.

Operates exclusively on anonymized medical records. Produces a *ranked set* of
candidate matches with confidence scores and constraint explanations - never a
single unilateral decision (human medical authority always has the final say).

The overall score is a weighted combination of:

- biological compatibility (ABO blood type + HLA antigen match)
- urgency (patient deterioration model output)
- geographic / transport feasibility (must beat organ cold-ischemia time)
- institutional readiness

Hard constraints (incompatible blood type, ineligible donor, organ mismatch,
transport time exceeding organ viability) eliminate a pair entirely.
"""

from __future__ import annotations

import math

from .schema import (
    BloodType,
    DonorRecord,
    GeoLocation,
    MatchCandidate,
    MedicalRecord,
    OrganType,
)

# Donor blood type -> set of recipient blood types it can donate to (ABO/Rh).
_ABO_COMPATIBILITY: dict[BloodType, frozenset[BloodType]] = {
    BloodType.O_NEG: frozenset(BloodType),  # universal donor
    BloodType.O_POS: frozenset(
        {BloodType.O_POS, BloodType.A_POS, BloodType.B_POS, BloodType.AB_POS}
    ),
    BloodType.A_NEG: frozenset(
        {BloodType.A_NEG, BloodType.A_POS, BloodType.AB_NEG, BloodType.AB_POS}
    ),
    BloodType.A_POS: frozenset({BloodType.A_POS, BloodType.AB_POS}),
    BloodType.B_NEG: frozenset(
        {BloodType.B_NEG, BloodType.B_POS, BloodType.AB_NEG, BloodType.AB_POS}
    ),
    BloodType.B_POS: frozenset({BloodType.B_POS, BloodType.AB_POS}),
    BloodType.AB_NEG: frozenset({BloodType.AB_NEG, BloodType.AB_POS}),
    BloodType.AB_POS: frozenset({BloodType.AB_POS}),
}

# Standard transplant HLA loci considered for matching.
_HLA_LOCI = 6

# Average ground/air medical transport speed (km/h) used for feasibility.
_TRANSPORT_SPEED_KMH = 250.0

# Scoring weights (sum to 1.0).
WEIGHTS = {
    "biological": 0.45,
    "urgency": 0.30,
    "geography": 0.15,
    "readiness": 0.10,
}


def abo_compatible(donor: BloodType, recipient: BloodType) -> bool:
    return recipient in _ABO_COMPATIBILITY[donor]


def haversine_km(a: GeoLocation, b: GeoLocation) -> float:
    radius = 6371.0
    lat1, lon1, lat2, lon2 = map(math.radians, (a.latitude, a.longitude, b.latitude, b.longitude))
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    h = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 2 * radius * math.asin(math.sqrt(h))


def transport_hours(donor: DonorRecord, patient: MedicalRecord) -> float:
    distance = haversine_km(donor.location, patient.location)
    # ~1h fixed handling/retrieval overhead in addition to travel time.
    return 1.0 + distance / _TRANSPORT_SPEED_KMH


def hla_match_fraction(donor: frozenset[str], patient: frozenset[str]) -> float:
    if not patient:
        return 0.0
    matches = len(donor & patient)
    return min(matches, _HLA_LOCI) / _HLA_LOCI


def _biological_score(donor: DonorRecord, patient: MedicalRecord) -> float:
    # ABO is a hard constraint handled upstream; here we reward HLA quality.
    return hla_match_fraction(donor.hla_antigens, patient.hla_antigens)


def _geography_score(donor: DonorRecord, patient: MedicalRecord) -> float:
    needed = transport_hours(donor, patient)
    budget = min(donor.organ_viability_hours, _max_ischemia(patient.needed_organ))
    if budget <= 0:
        return 0.0
    # Linear margin: full score when instant, zero when at the time budget.
    return max(0.0, 1.0 - needed / budget)


def _max_ischemia(organ: OrganType) -> float:
    from .schema import ORGAN_MAX_ISCHEMIA_HOURS

    return ORGAN_MAX_ISCHEMIA_HOURS[organ]


def hard_constraints(donor: DonorRecord, patient: MedicalRecord) -> list[str]:
    """Return a list of violated hard constraints (empty == eligible)."""
    violations: list[str] = []
    if not donor.eligible:
        violations.append("donor_ineligible")
    if donor.available_organ != patient.needed_organ:
        violations.append("organ_mismatch")
    if not abo_compatible(donor.blood_type, patient.blood_type):
        violations.append("abo_incompatible")
    needed = transport_hours(donor, patient)
    budget = min(donor.organ_viability_hours, _max_ischemia(patient.needed_organ))
    if needed > budget:
        violations.append("transport_exceeds_viability")
    return violations


def score_pair(donor: DonorRecord, patient: MedicalRecord) -> MatchCandidate | None:
    """Score a donor/patient pair. Returns None if a hard constraint fails."""
    violations = hard_constraints(donor, patient)
    if violations:
        return None

    components = {
        "biological": _biological_score(donor, patient),
        "urgency": _clamp(patient.urgency_score / 100.0),
        "geography": _geography_score(donor, patient),
        "readiness": _clamp(patient.institution_readiness),
    }
    score = sum(WEIGHTS[k] * v for k, v in components.items())

    # Confidence reflects how much real biological signal backed the score
    # (HLA + transport margin), independent of urgency weighting.
    confidence = _clamp(0.5 * components["biological"] + 0.5 * components["geography"])

    constraints = [f"transport_hours={transport_hours(donor, patient):.2f}"]
    return MatchCandidate(
        patient_token=patient.subject_token,
        donor_token=donor.subject_token,
        organ=patient.needed_organ,
        score=round(score, 4),
        confidence=round(confidence, 4),
        components={k: round(v, 4) for k, v in components.items()},
        constraints=constraints,
    )


def rank_matches(
    patient: MedicalRecord, donors: list[DonorRecord], *, limit: int = 10
) -> list[MatchCandidate]:
    """Return the ranked set of candidate donors for a patient."""
    candidates = [c for d in donors if (c := score_pair(d, patient)) is not None]
    candidates.sort(key=lambda c: c.score, reverse=True)
    return candidates[:limit]


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))
