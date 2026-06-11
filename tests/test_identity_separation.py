from __future__ import annotations

import pytest

from hopesync.identity_vault import IdentityResolutionDenied
from hopesync.schema import BloodType, OrganType, Role

from .conftest import AMS, identity


def test_pii_never_reaches_regional_node(network, clinician):
    token = network.edge.register_patient(
        clinician,
        identity=identity("Alice Patient"),
        blood_type=BloodType.A_POS,
        needed_organ=OrganType.KIDNEY,
        hla_antigens=frozenset({"A1"}),
        urgency_score=70.0,
        location=AMS,
    )
    record = network.node.patients[token]
    serialized = repr(record)
    assert "Alice Patient" not in serialized
    assert record.subject_token == token
    # The node store holds no IdentityData objects at all.
    assert not hasattr(record, "full_name")


def test_resolution_requires_approved_match(network, coordinator):
    token = network.vault.enroll(identity("Bob"))
    with pytest.raises(IdentityResolutionDenied):
        network.vault.resolve(token, actor="coord-1", role=Role.COORDINATOR, approved_match=False)


def test_resolution_denied_for_engineer(network):
    token = network.vault.enroll(identity("Carol"))
    with pytest.raises(IdentityResolutionDenied):
        network.vault.resolve(token, actor="eng-1", role=Role.ENGINEER, approved_match=True)


def test_resolution_succeeds_for_authorized_approved_match(network):
    data = identity("Dana")
    token = network.vault.enroll(data)
    resolved = network.vault.resolve(
        token, actor="clin-1", role=Role.CLINICIAN, approved_match=True
    )
    assert resolved.full_name == "Dana"
    # The resolution event is audited.
    actions = [e.action for e in network.audit.entries]
    assert "identity.resolve" in actions
