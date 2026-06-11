"""Hope Sync Medical Network - prototype coordination backend.

This package implements a focused, runnable slice of the Hope Sync architecture:

- A strict separation between Identity Data (PII) and Medical Data. Matching
  engines only ever see anonymized medical feature vectors.
- A regional matching engine that continuously ranks donor/patient
  compatibility using biological, urgency, and geographic feasibility scores.
- An append-only, cryptographically chained audit log for every action.
- Role-based access control and an Emergency Scan protocol.

It is intentionally a single-process prototype with in-memory storage so it can
be run and tested without external infrastructure, while preserving the
layering and security boundaries described in the engineering brief.
"""

__version__ = "0.1.0"
