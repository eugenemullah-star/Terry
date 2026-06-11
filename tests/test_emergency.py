from __future__ import annotations

import pytest

from hopesync.emergency import EmergencyError
from hopesync.schema import BloodType, OrganType

from .conftest import AMS, identity


def _register_pair(network, clinician, coordinator):
    patient_token = network.edge.register_patient(
        clinician,
        identity=identity("Patient"),
        blood_type=BloodType.A_POS,
        needed_organ=OrganType.KIDNEY,
        hla_antigens=frozenset({"A1", "B8"}),
        urgency_score=95.0,
        location=AMS,
    )
    network.edge.register_donor(
        coordinator,
        identity=identity("Donor"),
        blood_type=BloodType.O_NEG,
        available_organ=OrganType.KIDNEY,
        hla_antigens=frozenset({"A1", "B8"}),
        location=AMS,
    )
    return patient_token


def test_emergency_scan_returns_candidates(network, clinician, coordinator):
    token = _register_pair(network, clinician, coordinator)
    result = network.emergency.scan(clinician, token)
    assert result.candidates
    assert not result.is_expired()


def test_emergency_scan_unknown_patient(network, clinician):
    with pytest.raises(EmergencyError):
        network.emergency.scan(clinician, "nope")


def test_emergency_confirm_requires_coordinator(network, clinician, coordinator):
    token = _register_pair(network, clinician, coordinator)
    result = network.emergency.scan(clinician, token)
    # Clinician cannot approve (no APPROVE_MATCH permission).
    from hopesync.auth import AuthorizationError

    with pytest.raises(AuthorizationError):
        network.emergency.confirm(clinician, result.scan_id)
    confirmed = network.emergency.confirm(coordinator, result.scan_id)
    assert confirmed.confirmed


def test_emergency_results_expire(network, clinician, coordinator):
    network.emergency.ttl_seconds = 0.0  # immediate expiry
    token = _register_pair(network, clinician, coordinator)
    result = network.emergency.scan(clinician, token)
    assert result.is_expired()
    with pytest.raises(EmergencyError):
        network.emergency.confirm(coordinator, result.scan_id)


def test_emergency_does_not_bypass_hard_constraints(network, clinician, coordinator):
    # Patient needs a heart; only a far-away heart donor exists -> no candidates.
    from .conftest import SYDNEY

    token = network.edge.register_patient(
        clinician,
        identity=identity("HeartPatient"),
        blood_type=BloodType.A_POS,
        needed_organ=OrganType.HEART,
        hla_antigens=frozenset({"A1"}),
        urgency_score=99.0,
        location=AMS,
    )
    network.edge.register_donor(
        coordinator,
        identity=identity("FarHeart"),
        blood_type=BloodType.O_NEG,
        available_organ=OrganType.HEART,
        hla_antigens=frozenset({"A1"}),
        location=SYDNEY,
    )
    result = network.emergency.scan(clinician, token)
    assert result.candidates == []
