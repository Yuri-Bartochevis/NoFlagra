"""
A stand-in for Cloudflare R2, for developing the upload flow without an account.

    python cloud/scripts/mock_r2.py            # serves on :5002, files in ./r2-data

Then point the cloud app at it:

    export R2_ENDPOINT=http://localhost:5002
    export R2_BUCKET=noflagra-dev
    export R2_ACCESS_KEY_ID=dev
    export R2_SECRET_ACCESS_KEY=dev

boto3 will happily sign presigned URLs against this endpoint; this server just
ignores the signature. That is the one real difference from R2, and it's
deliberate — verifying SigV4 here would test botocore, not our code. Everything
else the flow depends on (PUT stores, HEAD reports the length, GET streams with
range support, 404 for a missing key) behaves the same way.

Do not run this anywhere that isn't your laptop: it authenticates nobody.
"""

import os
import sys

from flask import Flask, Response, jsonify, request, send_file

DATA_DIR = os.environ.get("MOCK_R2_DIR", os.path.join(os.getcwd(), "r2-data"))

app = Flask(__name__)


def _path_for(bucket, key):
    # Keys contain "/" and that's fine — they become real directories here.
    full = os.path.normpath(os.path.join(DATA_DIR, bucket, key))
    root = os.path.normpath(os.path.join(DATA_DIR, bucket))
    if not full.startswith(root):  # a key trying to climb out of the bucket
        return None
    return full


@app.route("/<bucket>/<path:key>", methods=["PUT"])
def put_object(bucket, key):
    path = _path_for(bucket, key)
    if path is None:
        return jsonify({"error": "bad key"}), 400
    os.makedirs(os.path.dirname(path), exist_ok=True)
    # Stream to disk rather than buffering: these are 300 MB files.
    with open(path, "wb") as fh:
        while True:
            chunk = request.stream.read(1024 * 1024)
            if not chunk:
                break
            fh.write(chunk)
    size = os.path.getsize(path)
    app.logger.info("PUT %s/%s (%d bytes)", bucket, key, size)
    return Response("", status=200, headers={"ETag": f'"{size}"'})


@app.route("/<bucket>/<path:key>", methods=["HEAD"])
def head_object(bucket, key):
    path = _path_for(bucket, key)
    if path is None or not os.path.isfile(path):
        return Response("", status=404)
    response = Response("", status=200, headers={"Content-Type": "video/mp4"})
    # A HEAD response has no body but must report the length a GET would
    # return. Werkzeug recomputes Content-Length from the (empty) body unless
    # told not to, which would report every object as 0 bytes — exactly the
    # kind of difference from real R2 that makes a stub worse than useless.
    response.automatically_set_content_length = False
    response.headers["Content-Length"] = str(os.path.getsize(path))
    return response


@app.route("/<bucket>/<path:key>", methods=["GET"])
def get_object(bucket, key):
    path = _path_for(bucket, key)
    if path is None or not os.path.isfile(path):
        return Response("NoSuchKey", status=404)
    # conditional=True gives range requests, which is what makes seeking work
    # in a <video> tag — same as real object storage.
    response = send_file(path, mimetype="video/mp4", conditional=True)
    disposition = request.args.get("response-content-disposition")
    if disposition:
        response.headers["Content-Disposition"] = disposition
    return response


@app.route("/<bucket>/<path:key>", methods=["DELETE"])
def delete_object(bucket, key):
    path = _path_for(bucket, key)
    if path and os.path.isfile(path):
        os.remove(path)
    return Response("", status=204)


@app.route("/", methods=["GET"])
def root():
    stored = []
    for base, _dirs, files in os.walk(DATA_DIR):
        for name in files:
            full = os.path.join(base, name)
            stored.append({
                "key": os.path.relpath(full, DATA_DIR),
                "bytes": os.path.getsize(full),
            })
    return jsonify({"backend": "mock-r2", "dir": DATA_DIR, "objects": stored})


if __name__ == "__main__":
    os.makedirs(DATA_DIR, exist_ok=True)
    port = int(os.environ.get("MOCK_R2_PORT", "5002"))
    print(f"mock R2 on http://localhost:{port}, storing in {DATA_DIR}", file=sys.stderr)
    app.run(host="127.0.0.1", port=port, threaded=True)
