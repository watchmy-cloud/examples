# examples

[![test](https://github.com/watchmy-cloud/examples/actions/workflows/test.yml/badge.svg)](https://github.com/watchmy-cloud/examples/actions/workflows/test.yml)

Code that receives [watchmy.cloud](https://watchmy.cloud) alerts. Every example runs its tests on each push.

## Webhook receivers

When a rule fires, we POST the alert as JSON to your URL. We sign each request. Your code checks the signature, answers 200, then acts on the alert.

| Language | Folder | Start |
|---|---|---|
| Python (Flask) | [`webhooks/python`](webhooks/python) | `pip install -r requirements.txt`<br>`WATCHMY_WEBHOOK_SECRET=... flask --app app run --port 8000` |
| Node (Express) | [`webhooks/node`](webhooks/node) | `npm install`<br>`WATCHMY_WEBHOOK_SECRET=... npm start` |

Both listen on `POST /watchmy-cloud`, port 8000. Each is about 50 lines.

## Check the signature

Every request carries three headers:

| Header | Example |
|---|---|
| `X-Watchmycloud-Timestamp` | `1790000000` |
| `X-Watchmycloud-Signature` | `v1=a44aa10e…` |
| `X-Watchmycloud-Api-Version` | `v1` |

1. Reject a timestamp more than 5 minutes old. That stops replays.
2. Compute HMAC-SHA256 of `<timestamp>.<raw body>`, keyed on your channel's secret. Prefix it with `v1=`.
3. Compare it with the signature header in constant time.

Use the raw request bytes. If you parse the JSON first and encode it again, the spacing changes and the match fails.

## Answer fast

We wait 10 seconds. A 2xx answer means done.

A 408, 429, 5xx or timeout means "try later". We retry after 1 minute, 5 minutes, 30 minutes and 2 hours. Any other 4xx means stop, so a bad signature gets a 401 and no retries.

A retry carries the same `alert_event_id`. Both examples skip an ID they have already seen.

## What the alert says

[`webhooks/payload-example.json`](webhooks/payload-example.json) is a full alert. The fields you will use most:

- `alert_event_id`: one per alert. Deduplicate on it.
- `alert.rule_type`: what fired, such as `daily_anomaly` or `hourly_spike`. Branch on this.
- `alert.over_usd` and `alert.top_drivers`: how much spend ran over, and which service drove it.
- `alert.message`: a sentence for people, in the account owner's language. Show it. Do not parse it.

Amounts come as strings, such as `"142.50"`, so no cent is lost to float rounding. Within version 1 we only add fields. Ignore the ones you don't know.

## Test your own receiver

[`webhooks/test-vector.json`](webhooks/test-vector.json) holds a secret, a timestamp, a body and the signature our production code gives them. Set your clock to that timestamp in a test. If your code accepts the vector, it will accept us.

Our own CI checks the same vector against the code that signs real alerts. If the format ever changes, we update it here first.

## Try it live

In the app, add a Webhook channel and paste your URL. We show the secret once. Then press **Send test message**. Your receiver needs a public HTTPS address. For a laptop, a tunnel such as `cloudflared` or `ngrok` works.

The first alert you see should be the test. The next one will be real money.
