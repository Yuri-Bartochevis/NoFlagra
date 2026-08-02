#!/usr/bin/env python3
"""
Issue a pairing code for a gym's Raspberry Pi.

    python3 scripts/create_pairing_code.py <establishment-slug> [--name "Front desk Pi"]

Prints a short code the gym types into edge/tools/pair_device.py. The code
is stored hashed and expires in PAIRING_CODE_LIFETIME (15 min); regenerating
it for a device that hasn't paired yet is fine, and replaces the old one.

Phase 2 has no dashboard UI for this on purpose — see docs/infrastructure.md.
"""

import argparse
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app  # noqa: E402
from app.extensions import db  # noqa: E402
from app.models import (  # noqa: E402
    PAIRING_CODE_LIFETIME,
    Device,
    Establishment,
    generate_pairing_code,
    hash_pairing_code,
)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("slug", help="establishment slug (see the establishments table)")
    parser.add_argument("--name", default="Gym Pi", help="human label for the device")
    args = parser.parse_args()

    app = create_app()
    with app.app_context():
        establishment = Establishment.query.filter_by(slug=args.slug).first()
        if establishment is None:
            sys.exit(f"No establishment with slug '{args.slug}'.")

        device = Device.query.filter_by(establishment_id=establishment.id).first()
        if device is not None and device.pairing_status == "paired":
            # One device per account for now. Re-pairing would orphan the
            # cameras and clips already hanging off this device.
            sys.exit(
                f"'{establishment.name}' already has a paired device "
                f"({device.uuid}). Un-pair it first."
            )

        if device is None:
            device = Device(establishment_id=establishment.id, name=args.name)
            db.session.add(device)
            db.session.flush()  # assign uuid/id before we print them

        code = generate_pairing_code()
        device.pairing_code_hash = hash_pairing_code(code)
        device.pairing_code_expires_at = datetime.now(timezone.utc) + PAIRING_CODE_LIFETIME
        device.pairing_status = "pending"
        db.session.commit()

        minutes = int(PAIRING_CODE_LIFETIME.total_seconds() // 60)
        print(f"\n  Establishment : {establishment.name}  ({establishment.slug})")
        print(f"  Device        : {device.name}  [{device.uuid}]")
        print(f"\n  PAIRING CODE  : {code}")
        print(f"  Expires in    : {minutes} minutes\n")
        print("  On the gym's Pi, run:")
        print(f"    python3 tools/pair_device.py <cloud-url> {code} <camera-name>...\n")


if __name__ == "__main__":
    main()
