import json
import os
import unittest
from pathlib import Path
from unittest.mock import patch

import app

VECTOR = json.loads((Path(__file__).parent.parent / "test-vector.json").read_text())
BODY = VECTOR["body"].encode()
TS = int(VECTOR["timestamp"])


class VerifyTest(unittest.TestCase):
    def check(self, **overrides):
        args = dict(secret=VECTOR["secret"], timestamp=VECTOR["timestamp"],
                    signature=VECTOR["signature"], raw_body=BODY, now=TS)
        args.update(overrides)
        return app.verify(**args)

    def test_accepts_the_test_vector(self):
        self.assertTrue(self.check())

    def test_rejects_a_changed_body(self):
        self.assertFalse(self.check(raw_body=BODY.replace(b"142.50", b"1.00")))

    def test_rejects_a_wrong_secret(self):
        self.assertFalse(self.check(secret="wrong"))

    def test_rejects_an_old_request(self):
        self.assertFalse(self.check(now=TS + 301))

    def test_rejects_missing_headers(self):
        self.assertFalse(self.check(timestamp=None))
        self.assertFalse(self.check(signature=None))


class ReceiveTest(unittest.TestCase):
    def post(self, body):
        headers = {"X-Watchmycloud-Timestamp": VECTOR["timestamp"],
                   "X-Watchmycloud-Signature": VECTOR["signature"],
                   "Content-Type": "application/json"}
        with patch.dict(os.environ, {"WATCHMY_WEBHOOK_SECRET": VECTOR["secret"]}), \
             patch("time.time", return_value=TS):
            return app.app.test_client().post("/watchmy-cloud", data=body, headers=headers)

    def test_signed_alert_gets_200_once_then_dedupes(self):
        app.seen_events.clear()
        self.assertEqual(self.post(BODY).status_code, 200)
        self.assertEqual(self.post(BODY).status_code, 200)
        self.assertEqual(len(app.seen_events), 1)

    def test_tampered_alert_gets_401(self):
        self.assertEqual(self.post(BODY.replace(b"Prod", b"Evil")).status_code, 401)


if __name__ == "__main__":
    unittest.main()
