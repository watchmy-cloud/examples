import json
import os
import unittest
from pathlib import Path
from unittest.mock import patch

import yaml

import forward

HERE = Path(__file__).parent
VECTOR = json.loads((HERE.parent / "webhooks" / "test-vector.json").read_text())
EVENT = json.loads(VECTOR["body"])
TS = int(VECTOR["timestamp"])


def lambda_event(body=VECTOR["body"], signature=VECTOR["signature"]):
    # The shape a Lambda function URL passes in. Header names arrive lowercased.
    return {"headers": {"x-watchmycloud-timestamp": VECTOR["timestamp"],
                        "x-watchmycloud-signature": signature},
            "body": body, "isBase64Encoded": False}


class HandlerTest(unittest.TestCase):
    def run_handler(self, target, target_status, event=None):
        env = {"WATCHMY_WEBHOOK_SECRET": VECTOR["secret"], "TARGET": target,
               "DESTINATION": "https://example.invalid/hook"}
        with patch.dict(os.environ, env), patch("time.time", return_value=TS), \
             patch.object(forward, "post", return_value=target_status) as post:
            result = forward.handler(event or lambda_event(), None)
        return result["statusCode"], post

    def test_forwards_a_signed_alert(self):
        for target in forward.FORMATS:
            with self.subTest(target):
                status, post = self.run_handler(target, 204)
                self.assertEqual(status, 200)
                post.assert_called_once()

    def test_rejects_a_bad_signature_without_calling_the_target(self):
        status, post = self.run_handler("discord", 204, lambda_event(signature="v1=00"))
        self.assertEqual(status, 401)
        post.assert_not_called()

    def test_asks_for_a_retry_when_the_target_is_down_or_busy(self):
        for target_status in (0, 429, 500, 503):
            with self.subTest(target_status):
                self.assertEqual(self.run_handler("teams", target_status)[0], 503)

    def test_reports_a_bad_destination_without_retries(self):
        self.assertEqual(self.run_handler("discord", 404)[0], 424)

    def test_pagerduty_goes_to_the_events_api(self):
        _, post = self.run_handler("pagerduty", 202)
        self.assertEqual(post.call_args.args[0], forward.PAGERDUTY_URL)


class FormatTest(unittest.TestCase):
    def test_pagerduty_dedups_on_the_alert_id(self):
        body = forward.pagerduty(EVENT, "key123")
        self.assertEqual(body["routing_key"], "key123")
        self.assertEqual(body["dedup_key"], EVENT["alert_event_id"])
        self.assertIn(body["payload"]["severity"], {"critical", "error", "warning", "info"})
        self.assertLessEqual(len(body["payload"]["summary"]), 1024)

    def test_discord_never_pings_anyone(self):
        body = forward.discord(EVENT, None)
        self.assertEqual(body["allowed_mentions"], {"parse": []})
        self.assertIn("$42.50", json.dumps(body))

    def test_teams_sends_an_adaptive_card_envelope(self):
        body = forward.teams(EVENT, None)
        self.assertEqual(body["type"], "message")
        attachment = body["attachments"][0]
        self.assertEqual(attachment["contentType"], "application/vnd.microsoft.card.adaptive")
        self.assertEqual(attachment["content"]["type"], "AdaptiveCard")

    def test_facts_name_the_service_that_grew(self):
        self.assertIn(("Driver", "Amazon Elastic Compute Cloud - Compute +$38.10"),
                      forward.facts(EVENT["alert"]))


class PostTest(unittest.TestCase):
    def test_sends_its_own_user_agent(self):
        # Cloudflare in front of Discord answers the default Python agent with 403.
        with patch("urllib.request.urlopen") as urlopen:
            urlopen.return_value.__enter__.return_value.status = 204
            self.assertEqual(forward.post("https://example.invalid", {}), 204)
        request = urlopen.call_args.args[0]
        self.assertEqual(request.get_header("User-agent"), forward.USER_AGENT)


class TemplateTest(unittest.TestCase):
    def test_template_carries_the_same_code(self):
        class Loader(yaml.SafeLoader):
            pass
        Loader.add_multi_constructor("!", lambda loader, suffix, node: None)
        template = yaml.load((HERE / "template.yaml").read_text(), Loader=Loader)
        inline = template["Resources"]["Function"]["Properties"]["Code"]["ZipFile"]
        self.assertEqual(inline, (HERE / "forward.py").read_text(),
                         "Copy forward.py into template.yaml (Code.ZipFile).")


if __name__ == "__main__":
    unittest.main()
