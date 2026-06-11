"""End-to-end demo: seed synthetic data and print ranked matches.

Run with:  python -m scripts.seed
"""

from __future__ import annotations

from hopesync.auth import Principal
from hopesync.network import build_network
from hopesync.schema import BloodType, GeoLocation, IdentityData, OrganType, Role

AMS = GeoLocation(latitude=52.37, longitude=4.89, hospital_id="ams")
BER = GeoLocation(latitude=52.52, longitude=13.40, hospital_id="ber")
PAR = GeoLocation(latitude=48.85, longitude=2.35, hospital_id="par")
SYD = GeoLocation(latitude=-33.87, longitude=151.21, hospital_id="syd")


def main() -> None:
    net = build_network()
    clinician = Principal(user_id="dr.smith", role=Role.CLINICIAN, hospital_id="ams")
    coordinator = Principal(user_id="coord.jones", role=Role.COORDINATOR, hospital_id="ams")
    auditor = Principal(user_id="gov.audit", role=Role.AUDITOR)

    patient_token = net.edge.register_patient(
        clinician,
        identity=IdentityData(full_name="Patient Zero", national_id="NL-0001"),
        blood_type=BloodType.A_POS,
        needed_organ=OrganType.KIDNEY,
        hla_antigens=frozenset({"A1", "B8", "DR3", "A2"}),
        urgency_score=88.0,
        location=AMS,
    )

    donors = [
        ("Local Match", BloodType.O_NEG, {"A1", "B8", "DR3"}, AMS, 22.0),
        ("Berlin Donor", BloodType.A_POS, {"A1", "B8"}, BER, 20.0),
        ("Paris Donor", BloodType.O_POS, {"A1"}, PAR, 18.0),
        ("Sydney Donor", BloodType.O_NEG, {"A1", "B8", "DR3", "A2"}, SYD, 24.0),
    ]
    for name, bt, hla, loc, viability in donors:
        net.edge.register_donor(
            coordinator,
            identity=IdentityData(full_name=name, national_id="ID-" + name.replace(" ", "")),
            blood_type=bt,
            available_organ=OrganType.KIDNEY,
            hla_antigens=frozenset(hla),
            location=loc,
            organ_viability_hours=viability,
        )

    print("=== Ranked matches for patient (anonymized tokens only) ===")
    for rank, c in enumerate(net.node.matches_for(clinician, patient_token), start=1):
        print(
            f"{rank}. donor={c.donor_token} score={c.score} "
            f"confidence={c.confidence} components={c.components} {c.constraints}"
        )

    print("\n=== Emergency scan ===")
    scan = net.emergency.scan(clinician, patient_token)
    print(
        f"scan_id={scan.scan_id} candidates={len(scan.candidates)} "
        f"expires_at={scan.expires_at():.0f}"
    )
    confirmed = net.emergency.confirm(coordinator, scan.scan_id)
    print(f"confirmed={confirmed.confirmed}")

    print("\n=== Identity resolution at final approved-match stage ===")
    identity = net.vault.resolve(
        patient_token, actor=clinician.user_id, role=Role.CLINICIAN, approved_match=True
    )
    print(f"resolved patient identity: {identity.full_name} ({identity.national_id})")

    print("\n=== Audit log (governance view) ===")
    audit = net.audit
    print(f"chain intact: {audit.verify()} | entries: {len(audit)}")
    for e in audit.entries:
        print(f"  #{e.index} {e.action} by {e.actor}")

    _ = auditor  # auditor role would access /audit in the API layer


if __name__ == "__main__":
    main()
