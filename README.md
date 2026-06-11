# Hope Sync Medical Network — Prototype

A runnable prototype of the **Hope Sync Medical Network**: a coordination
backend that securely matches patients in need of transplants with available
donors across a federated network of hospitals.

This is a focused, single-process implementation of the core architecture
described in the engineering brief. It is **not** production-ready and uses
in-memory storage with synthetic data only.

## What this prototype demonstrates

| Architectural principle (brief) | Where it lives |
| --- | --- |
| Hospital Edge Layer (interface/enforcement, no decisions) | `hopesync/edge.py` |
| Identity Data vs. Medical Data separation | `hopesync/identity_vault.py`, `hopesync/schema.py` |
| Regional Health Node with continuous matching | `hopesync/regional_node.py` |
| Matching engine (ABO + HLA + urgency + geo feasibility) | `hopesync/matching.py` |
| Append-only, cryptographically chained audit log | `hopesync/audit.py` |
| Role-based, zero-trust access control | `hopesync/auth.py` |
| Emergency Scan Protocol (time-bound results) | `hopesync/emergency.py` |
| REST API surface | `hopesync/api.py` |

### Key safety properties

- **PII never reaches the matching layer.** The Identity Vault returns an opaque
  `subject_token`; only that token flows to the regional node and matching
  engine. Identity is re-linked only at the final, approved-match stage by an
  authorized role, and every resolution is audited.
- **Every action is audited** into a tamper-evident hash chain. Modifying or
  deleting any historical entry breaks `AuditLog.verify()`.
- **Matching never decides unilaterally.** It returns a *ranked set* of
  candidates with confidence scores and constraint explanations.
- **Hard constraints cannot be bypassed**, including by emergency scans
  (ABO incompatibility, organ mismatch, transport time exceeding organ
  viability all eliminate a pair).

## Quickstart

```bash
# 1. Create the environment and install (uv recommended)
uv venv .venv && source .venv/bin/activate
uv pip install -e ".[dev]"

# 2. Run the test suite
pytest

# 3. Run the API
uvicorn hopesync.api:app --reload
# open http://127.0.0.1:8000/docs

# 4. Run the end-to-end demo (seeds data and prints ranked matches)
python -m scripts.seed
```

## API overview

All endpoints require `X-User-Id` and `X-Role` headers (simplified auth for the
prototype). Roles: `clinician`, `transplant_coordinator`, `hospital_admin`,
`regional_authority`, `auditor`, `engineer`.

| Method | Path | Required permission |
| --- | --- | --- |
| `POST` | `/patients` | `register_patient` |
| `POST` | `/donors` | `register_donor` |
| `GET` | `/patients/{token}/matches` | `view_matches` |
| `POST` | `/emergency/scan/{token}` | `trigger_emergency` |
| `POST` | `/emergency/confirm/{scan_id}` | `approve_match` |
| `GET` | `/audit` | `view_audit` |

### Example

```bash
curl -X POST http://127.0.0.1:8000/donors \
  -H 'X-User-Id: coord-1' -H 'X-Role: transplant_coordinator' \
  -H 'Content-Type: application/json' \
  -d '{
    "identity": {"full_name": "Jane Doe", "national_id": "NL-123"},
    "blood_type": "O-",
    "available_organ": "kidney",
    "hla_antigens": ["A1","B8","DR3"],
    "location": {"latitude": 52.37, "longitude": 4.89, "hospital_id": "h1"},
    "organ_viability_hours": 20
  }'
```

## Scope and limitations

This prototype deliberately collapses the four physical layers (Hospital Edge,
Regional Node, Global Core, Governance/Audit) into one process for
demonstrability. Cross-regional global coordination, real cryptographic
key domains, FHIR/HL7 gateways, persistence, and MFA/biometric auth are stubbed
or simplified. See the table above for the modeled boundaries.
