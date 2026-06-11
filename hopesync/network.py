"""Composition root.

Wires the layers into a single in-process network for the prototype:

    Hospital Edge -> Identity Vault (PII) + Regional Node (anonymized medical)
                  -> Matching Engine -> Emergency Coordinator
    All actions -> Audit Log
"""

from __future__ import annotations

from dataclasses import dataclass

from .audit import AuditLog
from .edge import HospitalEdge
from .emergency import EmergencyCoordinator
from .identity_vault import IdentityVault
from .regional_node import RegionalNode


@dataclass
class HopeSyncNetwork:
    region_id: str = "region-eu-west"
    hospital_id: str = "hospital-001"

    def __post_init__(self) -> None:
        self.audit = AuditLog()
        self.vault = IdentityVault(self.audit)
        self.node = RegionalNode(region_id=self.region_id, audit=self.audit)
        self.edge = HospitalEdge(hospital_id=self.hospital_id, vault=self.vault, node=self.node)
        self.emergency = EmergencyCoordinator(node=self.node)


def build_network() -> HopeSyncNetwork:
    return HopeSyncNetwork()
