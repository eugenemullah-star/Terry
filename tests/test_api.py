from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from hopesync import api
from hopesync.network import HopeSyncNetwork


@pytest.fixture
def client(monkeypatch):
    # Fresh network per test for isolation.
    net = HopeSyncNetwork()
    monkeypatch.setattr(api, "_network", net)
    return TestClient(api.app)


CLIN = {"X-User-Id": "clin-1", "X-Role": "clinician"}
COORD = {"X-User-Id": "coord-1", "X-Role": "transplant_coordinator"}
AUD = {"X-User-Id": "aud-1", "X-Role": "auditor"}
ENG = {"X-User-Id": "eng-1", "X-Role": "engineer"}

PATIENT = {
    "identity": {"full_name": "Alice", "national_id": "N1"},
    "blood_type": "A+",
    "needed_organ": "kidney",
    "hla_antigens": ["A1", "B8", "DR3"],
    "urgency_score": 90,
    "location": {"latitude": 52.37, "longitude": 4.89, "hospital_id": "ams"},
}
DONOR = {
    "identity": {"full_name": "Bob", "national_id": "N2"},
    "blood_type": "O-",
    "available_organ": "kidney",
    "hla_antigens": ["A1", "B8", "DR3"],
    "location": {"latitude": 52.37, "longitude": 4.89, "hospital_id": "ams"},
    "organ_viability_hours": 20,
}


def test_health(client):
    assert client.get("/health").json() == {"status": "ok"}


def test_full_flow(client):
    p = client.post("/patients", json=PATIENT, headers=CLIN)
    assert p.status_code == 200, p.text
    token = p.json()["subject_token"]

    d = client.post("/donors", json=DONOR, headers=COORD)
    assert d.status_code == 200, d.text

    m = client.get(f"/patients/{token}/matches", headers=CLIN)
    assert m.status_code == 200
    matches = m.json()
    assert len(matches) == 1
    assert matches[0]["patient_token"] == token


def test_engineer_forbidden(client):
    r = client.post("/patients", json=PATIENT, headers=ENG)
    assert r.status_code == 403


def test_emergency_flow(client):
    token = client.post("/patients", json=PATIENT, headers=CLIN).json()["subject_token"]
    client.post("/donors", json=DONOR, headers=COORD)
    scan = client.post(f"/emergency/scan/{token}", headers=CLIN)
    assert scan.status_code == 200
    scan_id = scan.json()["scan_id"]
    # Clinician cannot confirm.
    assert client.post(f"/emergency/confirm/{scan_id}", headers=CLIN).status_code == 403
    ok = client.post(f"/emergency/confirm/{scan_id}", headers=COORD)
    assert ok.status_code == 200 and ok.json()["confirmed"] is True


def test_audit_visibility_and_integrity(client):
    client.post("/patients", json=PATIENT, headers=CLIN)
    r = client.get("/audit", headers=AUD)
    assert r.status_code == 200
    body = r.json()
    assert body["intact"] is True
    assert any(e["action"] == "patient.ingest" for e in body["entries"])
    # Clinician cannot read the audit log.
    assert client.get("/audit", headers=CLIN).status_code == 403
