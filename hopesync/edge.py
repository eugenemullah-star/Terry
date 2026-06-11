"""Hospital Edge Layer.

The local interface between a hospital EHR and the Hope Sync network. It is an
interface and enforcement boundary with NO decision-making authority. Its job
here is to:

1. Accept raw intake containing both identity and medical fields.
2. Split identity (PII) into the Identity Vault, receiving an opaque token.
3. Forward only the anonymized :class:`MedicalRecord` / :class:`DonorRecord`
   (carrying the token, never PII) onward to the regional node.

This guarantees PII never leaves the edge toward the matching layers.
"""

from __future__ import annotations

from dataclasses import dataclass

from .auth import Principal
from .identity_vault import IdentityVault
from .regional_node import RegionalNode
from .schema import (
    BloodType,
    DonorRecord,
    GeoLocation,
    IdentityData,
    MedicalRecord,
    OrganType,
)


@dataclass
class HospitalEdge:
    hospital_id: str
    vault: IdentityVault
    node: RegionalNode

    def register_patient(
        self,
        principal: Principal,
        *,
        identity: IdentityData,
        blood_type: BloodType,
        needed_organ: OrganType,
        hla_antigens: frozenset[str],
        urgency_score: float,
        location: GeoLocation,
        institution_readiness: float = 1.0,
    ) -> str:
        token = self.vault.enroll(identity)
        record = MedicalRecord(
            subject_token=token,
            blood_type=blood_type,
            needed_organ=needed_organ,
            hla_antigens=hla_antigens,
            urgency_score=urgency_score,
            location=location,
            institution_readiness=institution_readiness,
        )
        self.node.ingest_patient(principal, record)
        return token

    def register_donor(
        self,
        principal: Principal,
        *,
        identity: IdentityData,
        blood_type: BloodType,
        available_organ: OrganType,
        hla_antigens: frozenset[str],
        location: GeoLocation,
        organ_viability_hours: float = 24.0,
        eligible: bool = True,
    ) -> str:
        token = self.vault.enroll(identity)
        record = DonorRecord(
            subject_token=token,
            blood_type=blood_type,
            available_organ=available_organ,
            hla_antigens=hla_antigens,
            location=location,
            organ_viability_hours=organ_viability_hours,
            eligible=eligible,
        )
        self.node.ingest_donor(principal, record)
        return token
