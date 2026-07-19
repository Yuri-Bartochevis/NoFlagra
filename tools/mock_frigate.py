"""
Stand-in for Frigate's API so the receiver can be tested with no camera,
no Docker and no NVR. Records every export request and prints the time range
in human-readable form.

    python tools/mock_frigate.py          # listens on :5000
"""

import os
from datetime import datetime

from flask import Flask, jsonify, request

app = Flask(__name__)
EXPORTS = []


@app.route("/api/version")
def version():
    return "0.17.2-mock"


@app.route("/api/export/<camera>/start/<int:start_ts>/end/<int:end_ts>", methods=["POST"])
def export(camera, start_ts, end_ts):
    body = request.get_json(silent=True) or {}
    span = end_ts - start_ts
    record = {
        "camera": camera,
        "start": start_ts,
        "end": end_ts,
        "span_seconds": span,
        "body": body,
    }
    EXPORTS.append(record)
    print(
        f"EXPORT {camera}: "
        f"{datetime.fromtimestamp(start_ts):%H:%M:%S} -> {datetime.fromtimestamp(end_ts):%H:%M:%S} "
        f"({span}s = {span / 60:.1f} min) name={body.get('name')}",
        flush=True,
    )
    return jsonify({"success": True, "message": "Starting export of recording.", "export_id": f"mock-{len(EXPORTS)}"})


@app.route("/exports")
def list_exports():
    return jsonify(EXPORTS)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), threaded=True)
