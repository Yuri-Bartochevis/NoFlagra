"""
Software stand-in for the ESP32 button box. Sends exactly what the firmware
sends, so you can test the whole chain before the hardware arrives.

    python tools/fake_button.py                       # one press
    python tools/fake_button.py --spam 5              # 5 presses, tests cooldown
    python tools/fake_button.py --host 192.168.1.50   # point at the Pi
"""

import argparse
import os
import sys
import time

import requests


def press(host, port, secret, timeout=10):
    url = f"http://{host}:{port}/save-clip"
    try:
        resp = requests.post(url, headers={"X-Auth-Token": secret}, json={}, timeout=timeout)
    except requests.RequestException as exc:
        print(f"  UNREACHABLE: {exc}")
        return None
    print(f"  HTTP {resp.status_code}  {resp.text.strip()}")
    return resp.status_code


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--host", default=os.environ.get("RECEIVER_HOST", "localhost"))
    p.add_argument("--port", type=int, default=int(os.environ.get("RECEIVER_PORT", 5001)))
    p.add_argument("--secret", default=os.environ.get("RECEIVER_SECRET", "change-me-to-something-random"))
    p.add_argument("--spam", type=int, default=1, help="number of presses")
    p.add_argument("--interval", type=float, default=1.0, help="seconds between presses")
    p.add_argument("--bad-token", action="store_true", help="send a wrong secret (expect 401)")
    args = p.parse_args()

    secret = "definitely-not-the-secret" if args.bad_token else args.secret

    print(f"Pressing button at {args.host}:{args.port} ({args.spam}x)")
    codes = []
    for i in range(args.spam):
        print(f"press {i + 1}:")
        codes.append(press(args.host, args.port, secret))
        if i + 1 < args.spam:
            time.sleep(args.interval)

    accepted = codes.count(202)
    print(f"\naccepted: {accepted}, cooled-down: {codes.count(429)}, rejected: {codes.count(401)}")
    sys.exit(0 if accepted or args.bad_token else 1)


if __name__ == "__main__":
    main()
