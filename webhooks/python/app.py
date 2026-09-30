"""Receive watchmy.cloud alerts over a webhook.

Run: WATCHMY_WEBHOOK_SECRET=... flask --app app run --port 8000
"""
import hashlib
import hmac
import os
import time

from flask import Flask, request

TOLERANCE_SECONDS = 300  # reject requests signed more than 5 minutes ago

app = Flask(__name__)
seen_events = set()  # use your database in production


def verify(secret, timestamp, signature, raw_body, now=None):
    """True if the request came from watchmy.cloud and is fresh."""
    try:
        age = abs((now or time.time()) - int(timestamp))
    except (TypeError, ValueError):
        return False
    if age > TOLERANCE_SECONDS:
        return False
    signed = f"{timestamp}.".encode() + raw_body
    expected = "v1=" + hmac.new(secret.encode(), signed, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature or "")


@app.post("/watchmy-cloud")
def receive():
    ok = verify(
        os.environ["WATCHMY_WEBHOOK_SECRET"],
        request.headers.get("X-Watchmycloud-Timestamp"),
        request.headers.get("X-Watchmycloud-Signature"),
        request.get_data(),  # the raw bytes, before any JSON parsing
    )
    if not ok:
        return "bad signature", 401

    event = request.get_json()
    if event["alert_event_id"] in seen_events:
        return "", 200  # a retry of an alert we already handled
    seen_events.add(event["alert_event_id"])

    alert = event["alert"]
    print(f"[{alert['account']['label']}] {alert['rule_type']}: {alert['message']}")
    return "", 200
