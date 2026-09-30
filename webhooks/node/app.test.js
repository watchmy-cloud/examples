const assert = require("node:assert");
const { test } = require("node:test");
const vector = require("../test-vector.json");
const { app, verify, seenEvents } = require("./app");

const body = Buffer.from(vector.body);
const ts = Number(vector.timestamp);
const check = (o = {}) => verify(
  o.secret ?? vector.secret, o.timestamp ?? vector.timestamp,
  "signature" in o ? o.signature : vector.signature, o.body ?? body, o.now ?? ts);

test("accepts the test vector", () => assert.ok(check()));
test("rejects a changed body", () =>
  assert.ok(!check({ body: Buffer.from(vector.body.replace("142.50", "1.00")) })));
test("rejects a wrong secret", () => assert.ok(!check({ secret: "wrong" })));
test("rejects an old request", () => assert.ok(!check({ now: ts + 301 })));
test("rejects missing headers", () => {
  assert.ok(!check({ timestamp: "" }));
  assert.ok(!check({ signature: undefined }));
});

test("signed alert gets 200 once, then dedupes; tampered gets 401", async (t) => {
  process.env.WATCHMY_WEBHOOK_SECRET = vector.secret;
  t.mock.method(Date, "now", () => ts * 1000);
  const server = app.listen(0);
  const url = `http://127.0.0.1:${server.address().port}/watchmy-cloud`;
  const post = (data) => fetch(url, {
    method: "POST", body: data,
    headers: { "Content-Type": "application/json",
      "X-Watchmycloud-Timestamp": vector.timestamp,
      "X-Watchmycloud-Signature": vector.signature },
  });
  try {
    seenEvents.clear();
    assert.strictEqual((await post(vector.body)).status, 200);
    assert.strictEqual((await post(vector.body)).status, 200);
    assert.strictEqual(seenEvents.size, 1);
    assert.strictEqual((await post(vector.body.replace("Prod", "Evil"))).status, 401);
  } finally {
    server.close();
  }
});
