from __future__ import annotations

import pytest

from hopesync.auth import Principal
from hopesync.network import HopeSyncNetwork
from hopesync.schema import (
    BloodType,
    DonorRecord,
    GeoLocation,
    IdentityData,
    MedicalRecord,
    OrganType,
    Role,
)

AMS = GeoLocation(latitude=52.37, longitude=4.89, hospital_id="ams")
BERLIN = GeoLocation(latitude=52.52, longitude=13.40, hospital_id="ber")
SYDNEY = GeoLocation(latitude=-33.87, longitude=151.21, hospital_id="syd")


@pytest.fixture
def network() -> HopeSyncNetwork:
    return HopeSyncNetwork()


@pytest.fixture
def clinician() -> Principal:
    return Principal(user_id="clin-1", role=Role.CLINICIAN, hospital_id="ams")


@pytest.fixture
def coordinator() -> Principal:
    return Principal(user_id="coord-1", role=Role.COORDINATOR, hospital_id="ams")


@pytest.fixture
def auditor() -> Principal:
    return Principal(user_id="aud-1", role=Role.AUDITOR)


def make_patient(token: str = "p1", **overrides) -> MedicalRecord:
    base = dict(
        subject_token=token,
        blood_type=BloodType.A_POS,
        needed_organ=OrganType.KIDNEY,
        hla_antigens=frozenset({"A1", "B8", "DR3"}),
        urgency_score=80.0,
        location=AMS,
        institution_readiness=1.0,
    )
    base.update(overrides)
    return MedicalRecord(**base)


def make_donor(token: str = "d1", **overrides) -> DonorRecord:
    base = dict(
        subject_token=token,
        blood_type=BloodType.O_NEG,
        available_organ=OrganType.KIDNEY,
        hla_antigens=frozenset({"A1", "B8", "DR3"}),
        location=AMS,
        eligible=True,
        organ_viability_hours=24.0,
    )
    base.update(overrides)
    return DonorRecord(**base)


def identity(name: str = "Test Person") -> IdentityData:
    return IdentityData(full_name=name, national_id="NID-" + name.replace(" ", ""))
