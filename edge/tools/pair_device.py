"""
Pair this Pi with its gym's NO FLAGRA account.

    python tools/pair_device.py https://noflagra.example 7K2P9QRM mat_camera
    python tools/pair_device.py https://noflagra.example 7K2P9QRM mat_camera "tatame 2"

An admin generates the code with cloud/scripts/create_pairing_code.py and
passes it along; it's good for 15 minutes and works exactly once.

On success the device key is written to .env next to RECEIVER_SECRET. The
cloud only ever stores its hash, so if you lose it the device has to be
re-paired — there is no way to read it back.
"""

import argparse
import os
import sys

import requests

ENV_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
MANAGED_KEYS = ("CLOUD_URL", "DEVICE_UUID", "DEVICE_KEY")


def write_env(path, values):
    """Set keys in a .env file, replacing existing lines and keeping the rest.

    Deliberately not python-dotenv's set_key: this keeps the tool
    dependency-free beyond `requests`, which the receiver already needs.
    """
    lines = []
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as fh:
            lines = fh.read().splitlines()

    for key, value in values.items():
        entry = f"{key}={value}"
        for i, line in enumerate(lines):
            if line.strip().startswith(f"{key}="):
                lines[i] = entry
                break
        else:
            lines.append(entry)

    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines).rstrip("\n") + "\n")
    # The device key is a credential — don't leave it world-readable.
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass


def pair(cloud_url, code, cameras, timeout=15):
    url = f"{cloud_url.rstrip('/')}/api/devices/pair"
    resp = requests.post(
        url, json={"code": code, "camera_names": cameras}, timeout=timeout
    )
    if resp.status_code != 201:
        try:
            detail = resp.json().get("error", resp.text)
        except ValueError:
            detail = resp.text
        raise SystemExit(f"Pairing failed (HTTP {resp.status_code}): {detail}")
    return resp.json()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("cloud_url", help="e.g. https://noflagra.example")
    parser.add_argument("code", help="pairing code from the admin")
    parser.add_argument(
        "cameras",
        nargs="+",
        help="camera names, matching the names in the Frigate config",
    )
    parser.add_argument("--env", default=ENV_PATH, help=f"env file to update (default: {ENV_PATH})")
    parser.add_argument("--print-only", action="store_true", help="don't touch .env")
    args = parser.parse_args()

    try:
        result = pair(args.cloud_url, args.code.strip().upper(), args.cameras)
    except requests.RequestException as exc:
        raise SystemExit(f"Could not reach {args.cloud_url}: {exc}")

    print(f"\n  Paired with : {result['establishment']}")
    print(f"  Device UUID : {result['device_uuid']}")
    for camera in result["cameras"]:
        print(f"  Camera      : {camera['name']}  ->  {camera['slug']}")

    values = {
        "CLOUD_URL": args.cloud_url.rstrip("/"),
        "DEVICE_UUID": result["device_uuid"],
        "DEVICE_KEY": result["device_key"],
    }

    if args.print_only:
        print("\n  Add these to .env yourself:\n")
        for key, value in values.items():
            print(f"    {key}={value}")
        print()
        return

    write_env(args.env, values)
    print(f"\n  Wrote {', '.join(MANAGED_KEYS)} to {args.env}")
    print("  Restart the receiver to pick them up.\n")


if __name__ == "__main__":
    main()
