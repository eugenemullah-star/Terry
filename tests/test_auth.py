from __future__ import annotations

import pytest

from hopesync.auth import AuthorizationError, Permission, Principal, authorize, has_permission
from hopesync.schema import BloodType, OrganType, Role

from .conftest import AMS, identity


def test_engineer_has_no_medical_permissions():
    for perm in Permission:
        assert not has_permission(Role.ENGINEER, perm)


def test_clinician_cannot_approve_match():
    clinician = Principal(user_id="c", role=Role.CLINICIAN)
    with pytest.raises(AuthorizationError):
        authorize(clinician, Permission.APPROVE_MATCH)


def test_mfa_required():
    p = Principal(user_id="c", role=Role.COORDINATOR, mfa_verified=False)
    with pytest.raises(AuthorizationError):
        authorize(p, Permission.VIEW_MATCHES)


def test_register_patient_denied_for_auditor(network, auditor):
    with pytest.raises(AuthorizationError):
        network.edge.register_patient(
            auditor,
            identity=identity("X"),
            blood_type=BloodType.A_POS,
            needed_organ=OrganType.KIDNEY,
            hla_antigens=frozenset(),
            urgency_score=10.0,
            location=AMS,
        )
