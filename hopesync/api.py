"""FastAPI application exposing the Hope Sync prototype.

Authentication is simplified for the prototype: callers present ``X-User-Id``
and ``X-Role`` headers, which are turned into a :class:`Principal`. In a real
deployment this would be MFA + biometric + device-bound credentials.
"""

from __future__ import annotations

import functools

from fastapi import Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel, Field

from .auth import AuthorizationError, Principal
from .emergency import EmergencyError
from .identity_vault import IdentityResolutionDenied
from .network import HopeSyncNetwork, build_network
from .schema import BloodType, GeoLocation, IdentityData, OrganType, Role

app = FastAPI(title="Hope Sync Medical Network", version="0.1.0")
_network: HopeSyncNetwork = build_network()


def get_network() -> HopeSyncNetwork:
    return _network


def get_principal(
    x_user_id: str = Header(...),
    x_role: str = Header(...),
    x_hospital_id: str | None = Header(default=None),
) -> Principal:
    try:
        role = Role(x_role)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"unknown role {x_role}") from exc
    return Principal(user_id=x_user_id, role=role, hospital_id=x_hospital_id)


# --------------------------------------------------------------------------
# Request / response models
# --------------------------------------------------------------------------


class IdentityIn(BaseModel):
    full_name: str
    national_id: str
    phone: str | None = None
    email: str | None = None


class LocationIn(BaseModel):
    latitude: float
    longitude: float
    hospital_id: str


class PatientIn(BaseModel):
    identity: IdentityIn
    blood_type: BloodType
    needed_organ: OrganType
    hla_antigens: list[str] = Field(default_factory=list)
    urgency_score: float = Field(ge=0, le=100)
    location: LocationIn
    institution_readiness: float = Field(default=1.0, ge=0, le=1)


class DonorIn(BaseModel):
    identity: IdentityIn
    blood_type: BloodType
    available_organ: OrganType
    hla_antigens: list[str] = Field(default_factory=list)
    location: LocationIn
    organ_viability_hours: float = Field(default=24.0, gt=0)
    eligible: bool = True


class TokenOut(BaseModel):
    subject_token: str


def _identity(data: IdentityIn) -> IdentityData:
    return IdentityData(
        full_name=data.full_name,
        national_id=data.national_id,
        phone=data.phone,
        email=data.email,
    )


def _location(data: LocationIn) -> GeoLocation:
    return GeoLocation(
        latitude=data.latitude, longitude=data.longitude, hospital_id=data.hospital_id
    )


def _guard(fn):  # type: ignore[no-untyped-def]
    """Translate domain exceptions into HTTP errors.

    ``functools.wraps`` sets ``__wrapped__`` so FastAPI's signature
    introspection still sees the original parameters for dependency injection.
    """

    @functools.wraps(fn)
    def wrapper(*args, **kwargs):  # type: ignore[no-untyped-def]
        try:
            return fn(*args, **kwargs)
        except AuthorizationError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        except IdentityResolutionDenied as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        except EmergencyError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=f"not found: {exc}") from exc

    return wrapper


# --------------------------------------------------------------------------
# Endpoints
# --------------------------------------------------------------------------


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/patients", response_model=TokenOut)
@_guard
def register_patient(
    body: PatientIn,
    principal: Principal = Depends(get_principal),
    net: HopeSyncNetwork = Depends(get_network),
) -> TokenOut:
    token = net.edge.register_patient(
        principal,
        identity=_identity(body.identity),
        blood_type=body.blood_type,
        needed_organ=body.needed_organ,
        hla_antigens=frozenset(body.hla_antigens),
        urgency_score=body.urgency_score,
        location=_location(body.location),
        institution_readiness=body.institution_readiness,
    )
    return TokenOut(subject_token=token)


@app.post("/donors", response_model=TokenOut)
@_guard
def register_donor(
    body: DonorIn,
    principal: Principal = Depends(get_principal),
    net: HopeSyncNetwork = Depends(get_network),
) -> TokenOut:
    token = net.edge.register_donor(
        principal,
        identity=_identity(body.identity),
        blood_type=body.blood_type,
        available_organ=body.available_organ,
        hla_antigens=frozenset(body.hla_antigens),
        location=_location(body.location),
        organ_viability_hours=body.organ_viability_hours,
        eligible=body.eligible,
    )
    return TokenOut(subject_token=token)


@app.get("/patients/{patient_token}/matches")
@_guard
def get_matches(
    patient_token: str,
    principal: Principal = Depends(get_principal),
    net: HopeSyncNetwork = Depends(get_network),
) -> list[dict]:
    candidates = net.node.matches_for(principal, patient_token)
    return [c.__dict__ for c in candidates]


@app.post("/emergency/scan/{patient_token}")
@_guard
def emergency_scan(
    patient_token: str,
    principal: Principal = Depends(get_principal),
    net: HopeSyncNetwork = Depends(get_network),
) -> dict:
    result = net.emergency.scan(principal, patient_token)
    return {
        "scan_id": result.scan_id,
        "patient_token": result.patient_token,
        "expires_at": result.expires_at(),
        "candidates": [c.__dict__ for c in result.candidates],
    }


@app.post("/emergency/confirm/{scan_id}")
@_guard
def emergency_confirm(
    scan_id: str,
    principal: Principal = Depends(get_principal),
    net: HopeSyncNetwork = Depends(get_network),
) -> dict:
    result = net.emergency.confirm(principal, scan_id)
    return {"scan_id": result.scan_id, "confirmed": result.confirmed}


@app.get("/audit")
@_guard
def get_audit(
    principal: Principal = Depends(get_principal),
    net: HopeSyncNetwork = Depends(get_network),
) -> dict:
    from .auth import Permission, authorize

    authorize(principal, Permission.VIEW_AUDIT)
    return {
        "intact": net.audit.verify(),
        "entries": [e.__dict__ for e in net.audit.entries],
    }
