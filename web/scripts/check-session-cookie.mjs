// The reviewer token lives in a cookie scripts cannot read, sent only over HTTPS beyond
// this computer, and only a well-formed token is ever forwarded to the API.
import assert from "node:assert/strict";
import {
  bearerFrom,
  clearedCookie,
  isLoopback,
  privateTransport,
  SESSION_COOKIE,
  sameOrigin,
  sessionCookie,
  validToken,
} from "../lib/session-cookie.ts";

const token = "weedz_12_AbC-d_e9";

for (const host of ["127.0.0.1:3270", "localhost", "localhost:3001", "[::1]:3001", "::1"]) {
  assert.ok(isLoopback(host), host);
}
for (const host of ["review.example.org", "10.0.0.5:3001", "localhost.example.org", ""]) {
  assert.ok(!isLoopback(host), host);
}

const local = sessionCookie(token, { host: "127.0.0.1:3270" });
assert.match(local, new RegExp(`^${SESSION_COOKIE}=${token};`));
for (const flag of ["HttpOnly", "SameSite=Strict", "Path=/", "Max-Age="]) {
  assert.ok(local.includes(flag), `${flag} in ${local}`);
}
assert.ok(!local.includes("Secure"), "plain http on this computer cannot set a Secure cookie");
assert.ok(sessionCookie(token, { host: "review.example.org" }).includes("; Secure"));
assert.ok(sessionCookie(token, { host: "127.0.0.1:3270", proto: "https" }).includes("; Secure"));
assert.match(clearedCookie({ host: "review.example.org" }), /Max-Age=0.*Secure/);

assert.ok(validToken(token));
for (const bad of [
  "",
  "weedz_x_y",
  "weedz_1_",
  "weedz_1_a b",
  "weedz_1_a;b",
  "a\r\nb",
  "x".repeat(300),
]) {
  assert.ok(!validToken(bad), JSON.stringify(bad));
}
assert.throws(() => sessionCookie("weedz_1_a;Domain=evil", { host: "localhost" }));

// A token must not cross the network in the clear: sign-in needs HTTPS beyond loopback.
assert.ok(privateTransport({ host: "127.0.0.1:3270" }));
assert.ok(privateTransport({ host: "review.example.org", proto: "https" }));
assert.ok(!privateTransport({ host: "review.example.org" }));
assert.ok(!privateTransport({ host: "review.example.org", proto: "http" }));

const fetched = (site) => ({ headers: { get: () => site } });
assert.ok(sameOrigin(fetched(null)) && sameOrigin(fetched("same-origin")));
assert.ok(!sameOrigin(fetched("cross-site")) && !sameOrigin(fetched("same-site")));

assert.equal(bearerFrom(`other=1;${SESSION_COOKIE}=${token}`), `Bearer ${token}`);
assert.equal(bearerFrom(`${SESSION_COOKIE}=not-a-token`), undefined);
assert.equal(bearerFrom(null), undefined);
console.log("Session cookie checks passed.");
