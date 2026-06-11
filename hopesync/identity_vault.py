"""Identity Vault.

Stores Identity Data (PII) keyed by an opaque ``subject_token``. The token is
the ONLY value shared with the medical/matching layers. Identity resolution is
permitted exclusively at the final stage of an approved match, by authorized
personnel, and every resolution is audited.
"""

from __future__ import annotations

import secrets

from .audit import AuditLog
from .schema import IdentityData, Role

# Roles permitted to resolve a token back to identity (final match stage).
_RESOLUTION_ROLES = frozenset({Role.CLINICIAN, Role.COORDINATOR})


class IdentityResolutionDenied(Exception):
    """Raised when a caller is not authorized to resolve an identity."""


class IdentityVault:
    def __init__(self, audit: AuditLog) -> None:
        self._store: dict[str, IdentityData] = {}
        self._audit = audit

    def enroll(self, identity: IdentityData) -> str:
        """Store identity data and return its opaque subject token."""
        token = "subj_" + secrets.token_hex(8)
        self._store[token] = identity
        self._audit.record(
            actor="identity_vault",
            action="identity.enroll",
            details={"subject_token": token},
        )
        return token

    def resolve(self, token: str, *, actor: str, role: Role, approved_match: bool) -> IdentityData:
        """Resolve a token to identity. Only allowed for an approved match."""
        if role not in _RESOLUTION_ROLES:
            self._audit.record(
                actor=actor,
                action="identity.resolve.denied",
                details={"subject_token": token, "reason": "role"},
            )
            raise IdentityResolutionDenied(f"role {role.value} may not resolve identity")
        if not approved_match:
            self._audit.record(
                actor=actor,
                action="identity.resolve.denied",
                details={"subject_token": token, "reason": "unapproved_match"},
            )
            raise IdentityResolutionDenied("identity resolution requires an approved match")
        if token not in self._store:
            raise KeyError(token)
        self._audit.record(
            actor=actor,
            action="identity.resolve",
            details={"subject_token": token},
        )
        return self._store[token]

    def __contains__(self, token: str) -> bool:
        return token in self._store
