# forward

Send watchmy.cloud alerts to Microsoft Teams, Discord or PagerDuty.

This is one AWS Lambda function with a public URL. We sign each alert and send it there. The function checks the signature, reshapes the alert for your tool and passes it on. It uses the Python standard library and nothing else, so there is nothing to install or patch.

## What you get

- **Teams**: a card with the account, the rule, how much spend ran over and which service drove it, plus a button to the alert.
- **Discord**: the same facts as an embed. It can never ping `@everyone`.
- **PagerDuty**: an incident. Its dedup key is the alert ID, so a retry updates the incident and never opens a second one.

## Before you start

Get the address of the place alerts should land:

- **Teams**: in the channel, open **⋯ → Workflows**, pick **Send webhook alerts to a channel**, save, and copy the webhook link.
- **Discord**: **Server Settings → Integrations → Webhooks → New Webhook**, pick the channel, then **Copy Webhook URL**.
- **PagerDuty**: in the service, **Integrations → Add an integration → Events API V2**, then copy the **Integration Key**.

## Deploy

You need the AWS CLI and credentials for your account. Four steps, about five minutes.

**1. Create the function.** The secret does not exist yet, so start with a placeholder.

```bash
aws cloudformation deploy \
  --template-file template.yaml \
  --stack-name watchmy-cloud-forward \
  --capabilities CAPABILITY_IAM \
  --parameter-overrides WebhookSecret=placeholder Target=discord Destination='<your URL or key>'
```

Set `Target` to `teams`, `discord` or `pagerduty`.

**2. Get its URL.**

```bash
aws cloudformation describe-stacks --stack-name watchmy-cloud-forward \
  --query "Stacks[0].Outputs[?OutputKey=='WebhookUrl'].OutputValue" --output text
```

**3. Add a Webhook channel** in watchmy.cloud with that URL. We show the signing secret once. Copy it.

**4. Swap in the real secret.** Run step 1 again with `WebhookSecret=<the secret>`. Then press **Send test message** in the app. It should land in your channel within a few seconds.

## When something fails

The function tells us what happened, and we act on it:

| Your tool answers | The function returns | We do |
|---|---|---|
| Success | `200` | Mark the alert delivered. |
| Busy (`429`), down (`5xx`) or no answer | `503` | Retry after 1 min, 5 min, 30 min and 2 h. |
| Rejected (`4xx`), such as a wrong URL or key | `424` | Stop, and show the error in your delivery history. |
| Bad or old signature | `401` | Stop. Nothing reaches your tool. |

Teams and Discord have no dedup key. If your tool accepts an alert but answers after our 10-second timeout, a retry can post it twice. PagerDuty never does.

PagerDuty accepts any well-formed integration key, even one that does not exist, and answers with success. A typo in the key still reads "delivered" in our history. After **Send test message**, check that the incident opened.

## What it costs

One Lambda call per alert, plus one per retry. At a few alerts a day that is well under a cent a month. The URL is public, but a request without our signature ends in a few milliseconds.

## Remove it

```bash
aws cloudformation delete-stack --stack-name watchmy-cloud-forward
```

Delete the Webhook channel in the app too.

## Change the code

`template.yaml` carries the same code as `forward.py`, inline. If you edit one, copy it into the other. The tests fail when they differ.
