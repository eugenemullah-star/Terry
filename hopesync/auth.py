"""Role-based access control (zero-trust style).

Every operation is authorized against an explicit permission map before
execution. There is no implicit trust between components: callers must present a
:class:`Principal`, and the requested :class:`Permission` is checked here.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass

from .schema import Role


class Permission(enum.StrEnum):
    REGISTER_PATIENT = "register_patient"
    REGISTER_DONOR = "register_donor"
    VIEW_MATCHES = "view_matches"
    TRIGGER_EMERGENCY = "trigger_emergency"
    APPROVE_MATCH = "approve_match"
    VIEW_AUDIT = "view_audit"
    MANAGE_INSTITUTION = "manage_institution"


_ROLE_PERMISSIONS: dict[Role, frozenset[Permission]] = {
    Role.CLINICIAN: frozenset(
        {
            Permission.REGISTER_PATIENT,
            Permission.VIEW_MATCHES,
            Permission.TRIGGER_EMERGENCY,
        }
    ),
    Role.COORDINATOR: frozenset(
        {
            Permission.REGISTER_PATIENT,
            Permission.REGISTER_DONOR,
            Permission.VIEW_MATCHES,
            Permission.APPROVE_MATCH,
            Permission.TRIGGER_EMERGENCY,
        }
    ),
    Role.HOSPITAL_ADMIN: frozenset({Permission.MANAGE_INSTITUTION}),
    Role.REGIONAL_AUTHORITY: frozenset({Permission.VIEW_AUDIT, Permission.MANAGE_INSTITUTION}),
    Role.AUDITOR: frozenset({Permission.VIEW_AUDIT}),
    # Engineers explicitly cannot read medical data or matches.
    Role.ENGINEER: frozenset(),
}


@dataclass(frozen=True)
class Principal:
    user_id: str
    role: Role
    hospital_id: str | None = None
    mfa_verified: bool = True


class AuthorizationError(Exception):
    pass


def has_permission(role: Role, permission: Permission) -> bool:
    return permission in _ROLE_PERMISSIONS.get(role, frozenset())


def authorize(principal: Principal, permission: Permission) -> None:
    if not principal.mfa_verified:
        raise AuthorizationError("multi-factor authentication required")
    if not has_permission(principal.role, permission):
        raise AuthorizationError(
            f"role {principal.role.value} lacks permission {permission.value}"
        )
