import assert from "node:assert/strict";
import { backendOrigin, privateHeaders, reviewJson, sessionOrigin } from "../lib/review-service.ts";

const deployed = (value) => backendOrigin({ WEEDZ_DEPLOYMENT: "beast", WEEDZ_API_URL: value });
assert.equal(backendOrigin({}), "http://127.0.0.1:8000");
assert.equal(backendOrigin({ WEEDZ_API_URL: "http://127.0.0.1:8022/" }), "http://127.0.0.1:8022");
assert.equal(deployed("https://api.example.test/"), "https://api.example.test");
for (const value of [
  undefined,
  "",
  "http://api.example.test",
  "https://localhost",
  "https://127.1",
  "https://[::1]",
  "https://0.0.0.0",
  "https://192.168.1.1",
  "https://api.example.test/path",
  "https://api.example.test/?token=hidden-secret",
  "https://hidden-secret@api.example.test",
  "https://api.example.test/#hidden-secret",
  "not-a-url",
  "https://api.example.test:bad",
]) {
  assert.throws(
    () => deployed(value),
    (error) => {
      assert(!error.message.includes("hidden-secret"));
      return true;
    },
    `must refuse ${value === undefined ? "missing origin" : "unsafe origin"}`,
  );
}
const headers = privateHeaders({
  "Content-Type": "image/png",
  "Content-Disposition": 'attachment; filename="evidence.png"',
});
assert.equal(headers.get("Cache-Control"), "private, no-store");
assert.equal(headers.get("Vary"), "Cookie");
assert.equal(headers.get("Content-Type"), "image/png");
assert.equal(headers.get("Content-Disposition"), 'attachment; filename="evidence.png"');
const response = reviewJson(
  { signed_out: true },
  { status: 401, headers: { "Set-Cookie": "redacted-test" } },
);
assert.equal(response.status, 401);
assert.equal(response.headers.get("Cache-Control"), "private, no-store");
assert.equal(response.headers.get("Set-Cookie"), "redacted-test");
console.log("Deployment origins fail closed; private review responses cannot enter shared caches.");

assert.equal(deployed("http://127.0.0.1:8058"), "http://127.0.0.1:8058");
assert.equal(sessionOrigin(new Request("https://review.example.test/api/session")).proto, "https");
assert.equal(
  sessionOrigin(
    new Request("http://127.0.0.1/api/session", { headers: { "x-forwarded-proto": "https" } }),
  ).proto,
  "https",
);
assert.equal(privateHeaders({ Vary: "Accept-Encoding" }).get("Vary"), "Accept-Encoding, Cookie");
