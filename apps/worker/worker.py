import os
import socket
import time

import redis

r = redis.Redis(
    host=os.environ.get("REDIS_HOST", "redis"),
    port=6379,
    decode_responses=True,
    socket_timeout=30,
    socket_connect_timeout=5,
)
work_seconds = float(os.environ.get("WORK_SECONDS", "0.5"))
name = socket.gethostname()

print(f"worker {name} started, work_seconds={work_seconds}", flush=True)
while True:
    try:
        item = r.blpop("jobs", timeout=5)
    except (redis.exceptions.ConnectionError, redis.exceptions.TimeoutError) as e:
        print(f"{name} redis error: {e}; retrying in 1s", flush=True)
        time.sleep(1)
        continue
    if item is None:
        continue
    time.sleep(work_seconds)
    r.incr("processed")
    print(f"{name} processed a job", flush=True)
