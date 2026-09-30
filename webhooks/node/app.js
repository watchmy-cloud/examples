// Receive watchmy.cloud alerts over a webhook.
// Run: WATCHMY_WEBHOOK_SECRET=... node app.js
const crypto = require("node:crypto");
const express = require("express");

const TOLERANCE_SECONDS = 300; // reject requests signed more than 5 minutes ago
const seenEvents = new Set(); // use your database in production

function verify(secret, timestamp, signature, rawBody, now = Date.now() / 1000) {
  if (!(Math.abs(now - Number(timestamp)) <= TOLERANCE_SECONDS)) return false;
  const signed = Buffer.concat([Buffer.from(`${timestamp}.`), rawBody]);
  const expected = Buffer.from(
    "v1=" + crypto.createHmac("sha256", secret).update(signed).digest("hex"));
  const given = Buffer.from(signature || "");
  // timingSafeEqual throws on unequal lengths, so check first.
  return given.length === expected.length && crypto.timingSafeEqual(expected, given);
}

const app = express();

// express.raw keeps the exact bytes we signed. Parse JSON only after verifying.
app.post("/watchmy-cloud", express.raw({ type: "application/json" }), (req, res) => {
  const ok = verify(
    process.env.WATCHMY_WEBHOOK_SECRET,
    req.get("X-Watchmycloud-Timestamp"),
    req.get("X-Watchmycloud-Signature"),
    req.body,
  );
  if (!ok) return res.status(401).send("bad signature");

  const event = JSON.parse(req.body);
  if (seenEvents.has(event.alert_event_id)) return res.sendStatus(200); // a retry
  seenEvents.add(event.alert_event_id);

  const { alert } = event;
  console.log(`[${alert.account.label}] ${alert.rule_type}: ${alert.message}`);
  res.sendStatus(200);
});

if (require.main === module) app.listen(8000, () => console.log("Listening on :8000"));

module.exports = { app, verify, seenEvents };
