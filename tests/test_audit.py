from __future__ import annotations

from dataclasses import replace

from hopesync.audit import GENESIS_HASH, AuditLog


def test_chain_links_and_verifies():
    log = AuditLog()
    log.record("a", "action.one")
    log.record("b", "action.two", {"k": "v"})
    assert len(log) == 2
    assert log.entries[0].prev_hash == GENESIS_HASH
    assert log.entries[1].prev_hash == log.entries[0].entry_hash
    assert log.verify()


def test_tamper_detection():
    log = AuditLog()
    log.record("a", "action.one")
    log.record("b", "action.two")
    # Tamper with a historical entry's content without recomputing the chain.
    log._entries[0] = replace(log._entries[0], action="action.tampered")
    assert not log.verify()


def test_tamper_with_hash_detected():
    log = AuditLog()
    log.record("a", "x")
    log._entries[0] = replace(log._entries[0], entry_hash="deadbeef")
    assert not log.verify()
