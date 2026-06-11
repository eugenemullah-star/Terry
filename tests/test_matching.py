from __future__ import annotations

from hopesync.matching import (
    abo_compatible,
    hard_constraints,
    hla_match_fraction,
    rank_matches,
    score_pair,
)
from hopesync.schema import BloodType, OrganType

from .conftest import AMS, SYDNEY, make_donor, make_patient


def test_abo_universal_donor():
    for recipient in BloodType:
        assert abo_compatible(BloodType.O_NEG, recipient)


def test_abo_incompatible():
    assert not abo_compatible(BloodType.AB_POS, BloodType.O_NEG)
    assert not abo_compatible(BloodType.A_POS, BloodType.B_POS)


def test_hla_fraction():
    assert hla_match_fraction(frozenset({"A1", "B8", "DR3"}), frozenset({"A1", "B8", "DR3"})) == 0.5
    assert hla_match_fraction(frozenset(), frozenset({"A1"})) == 0.0
    assert hla_match_fraction(frozenset({"A1"}), frozenset()) == 0.0


def test_score_pair_perfect_local_match():
    patient = make_patient()
    donor = make_donor()
    candidate = score_pair(donor, patient)
    assert candidate is not None
    assert candidate.organ == OrganType.KIDNEY
    assert 0.0 < candidate.score <= 1.0
    assert candidate.components["urgency"] == 0.8


def test_hard_constraint_abo_blocks():
    patient = make_patient(blood_type=BloodType.O_NEG)
    donor = make_donor(blood_type=BloodType.AB_POS)
    assert "abo_incompatible" in hard_constraints(donor, patient)
    assert score_pair(donor, patient) is None


def test_hard_constraint_organ_mismatch():
    patient = make_patient(needed_organ=OrganType.HEART)
    donor = make_donor(available_organ=OrganType.KIDNEY)
    assert "organ_mismatch" in hard_constraints(donor, patient)


def test_hard_constraint_ineligible_donor():
    assert "donor_ineligible" in hard_constraints(make_donor(eligible=False), make_patient())


def test_transport_exceeds_viability_for_heart_across_globe():
    # Heart has a 4h ischemia budget; Amsterdam <-> Sydney is far beyond it.
    patient = make_patient(needed_organ=OrganType.HEART, location=AMS)
    donor = make_donor(available_organ=OrganType.HEART, location=SYDNEY)
    assert "transport_exceeds_viability" in hard_constraints(donor, patient)
    assert score_pair(donor, patient) is None


def test_closer_donor_ranks_higher():
    patient = make_patient()
    near = make_donor(token="near", location=AMS)
    # Same everything but farther away -> lower geography score.
    far = make_donor(token="far", location=SYDNEY, organ_viability_hours=24.0)
    ranked = rank_matches(patient, [far, near])
    assert ranked[0].donor_token == "near"


def test_rank_excludes_incompatible():
    patient = make_patient(blood_type=BloodType.O_NEG)
    good = make_donor(token="good", blood_type=BloodType.O_NEG)
    bad = make_donor(token="bad", blood_type=BloodType.AB_POS)
    ranked = rank_matches(patient, [good, bad])
    tokens = {c.donor_token for c in ranked}
    assert tokens == {"good"}
