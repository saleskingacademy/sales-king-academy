#!/usr/bin/env python3
"""
SKA second-level heartbeat driver.

Cloudflare Cron Triggers cannot fire faster than once per minute
(`* * * * *` is the floor) and give only 10ms CPU on the free plan.
A GitHub Actions runner has neither limit: a single job runs up to
6 hours, so a Python loop can tick every second for 21,600 ticks and
four chained jobs cover a full day.

This process is a CLOCK, not a compute plane. It does no inference and
holds no state - it only fires the worker's own trigger endpoint on the
beat. All work stays in the Worker, where waiting on fetch/KV/D1 does
not count against CPU time.

Beat alignment: ticks are anchored to the SKA genesis
(1530403200 = 2018-07-01T00:00:00Z), so tick N lands on real beat
boundaries rather than drifting from process start. 1 Beat = 1 second
elapsed since genesis.
"""

import os
import sys
import time
import json
import urllib.request
import urllib.error
import threading

GENESIS = 1530403200  # 2018-07-01T00:00:00Z

BASE = os.environ.get(
    "SKA_WORKER_URL",
    "https://sales-king-academy.saleskingacademy.workers.dev",
).rstrip("/")
HB_KEY = os.environ.get("SKA_HEARTBEAT_KEY", "")
TICK = float(os.environ.get("TICK_SECONDS", "1"))
RUN_MINUTES = float(os.environ.get("RUN_MINUTES", "330"))  # 5.5h, under the 6h cap
ENDPOINT = os.environ.get("SKA_TICK_PATH", "/api/heartbeat/trigger")

# Workers Free allows 100,000 requests/day. A 1s tick is 86,400 - 86% of the
# budget before a single user loads a page. Stop well short and let the
# Cloudflare cron carry the remainder.
DAILY_BUDGET = int(os.environ.get("DAILY_REQUEST_BUDGET", "60000"))

_lock = threading.Lock()
MAX_INFLIGHT = int(os.environ.get("MAX_INFLIGHT", "24"))
skipped_inflight = 0
sent = 0
ok = 0
fail = 0
consecutive_fail = 0
started = time.time()
deadline = started + RUN_MINUTES * 60


def beat_now() -> int:
    return int(time.time()) - GENESIS


def fire(beat: int):
    """Fire one tick. Returns (success, detail)."""
    body = json.dumps({"beat": beat, "source": "gh-actions-python", "tick": TICK}).encode()
    req = urllib.request.Request(BASE + ENDPOINT, data=body, method="POST")
    req.add_header("Content-Type", "application/json")
    req.add_header("User-Agent", "ska-heartbeat/1.0")
    if HB_KEY:
        req.add_header("X-Heartbeat-Key", HB_KEY)
    try:
        with urllib.request.urlopen(req, timeout=max(5, TICK * 8)) as r:
            return True, r.status
    except urllib.error.HTTPError as e:
        return False, "HTTP %d" % e.code
    except Exception as e:
        return False, type(e).__name__


print("SKA heartbeat | tick=%ss | run=%smin | endpoint=%s" % (TICK, RUN_MINUTES, ENDPOINT), flush=True)
print("genesis beat at start: %d" % beat_now(), flush=True)

# Anchor to the beat grid so ticks land on second boundaries, not on
# whenever this process happened to start.
next_at = (int(time.time() / TICK) + 1) * TICK

while time.time() < deadline:
    now = time.time()
    if now < next_at:
        time.sleep(min(next_at - now, 5.0))
        continue

    # Drift correction: if we fell behind (runner pause, slow response),
    # skip to the next real boundary instead of firing a burst to catch up.
    missed = 0
    while next_at <= time.time():
        next_at += TICK
        missed += 1
    if missed > 1:
        print("  drift: skipped %d tick(s)" % (missed - 1), flush=True)

    if sent >= DAILY_BUDGET:
        print("request budget reached (%d) - stopping early" % DAILY_BUDGET, flush=True)
        break

    beat = beat_now()
    # Fire in a background thread. The worker's trigger endpoint can take
    # several seconds, and waiting for it serially caps the tick rate at the
    # response time - measured 5s/tick when blocking, which defeats a 1s beat.
    # The clock must not be bound by the work it starts.
    def _shoot(b=beat):
        global ok, fail, consecutive_fail
        good, detail = fire(b)
        with _lock:
            if good:
                ok += 1
                consecutive_fail = 0
            else:
                fail += 1
                consecutive_fail += 1
                if consecutive_fail <= 3 or consecutive_fail % 50 == 0:
                    print("  beat %d FAILED: %s (streak %d)" % (b, detail, consecutive_fail), flush=True)
    if threading.active_count() < MAX_INFLIGHT:
        threading.Thread(target=_shoot, daemon=True).start()
        sent += 1
    else:
        skipped_inflight += 1
        sent += 0

    if False:
        pass
    elif False:
        consecutive_fail += 1
        if consecutive_fail <= 3 or consecutive_fail % 50 == 0:
            print("  tick %d beat %d FAILED: %s (streak %d)" % (sent, beat, detail, consecutive_fail), flush=True)
        # Exponential backoff so a down worker is not hammered for 5 hours.
    if consecutive_fail >= 5:
        backoff = min(30.0, TICK * (2 ** min(consecutive_fail - 4, 5)))
        time.sleep(backoff)
        next_at = (int(time.time() / TICK) + 1) * TICK
    if consecutive_fail >= 200:
        print("200 consecutive failures - aborting", flush=True)
        break

    if sent % 300 == 0:
        el = time.time() - started
        print("  %d ticks | ok %d | fail %d | %.1f min elapsed | beat %d"
              % (sent, ok, fail, el / 60.0, beat), flush=True)

time.sleep(min(10.0, TICK * 5))   # let in-flight ticks land
el = time.time() - started
print("", flush=True)
print("=== HEARTBEAT SUMMARY ===", flush=True)
print("  ticks sent : %d" % sent, flush=True)
print("  skipped (inflight cap): %d" % skipped_inflight, flush=True)
print("  ok / fail  : %d / %d" % (ok, fail), flush=True)
print("  elapsed    : %.1f min" % (el / 60.0), flush=True)
print("  final beat : %d" % beat_now(), flush=True)
if sent and ok / sent < 0.5:
    print("  MORE THAN HALF OF TICKS FAILED", flush=True)
    sys.exit(1)
