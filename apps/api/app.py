import json
import os
import socket
import time

import redis
from flask import Flask, jsonify, request

r = redis.Redis(host=os.environ.get("REDIS_HOST", "redis"), port=6379, decode_responses=True)
app = Flask(__name__)


@app.get("/healthz")
def healthz():
    return "ok"


@app.post("/jobs")
def add_jobs():
    n = int(request.args.get("n", 1))
    for _ in range(n):
        r.rpush("jobs", json.dumps({"created": time.time()}))
    return jsonify(queued=n, pod=socket.gethostname())


@app.get("/stats")
def stats():
    return jsonify(
        pending=r.llen("jobs"),
        processed=int(r.get("processed") or 0),
        pod=socket.gethostname(),
    )
