"use client";

import { type FormEvent, useState } from "react";

/** Exchange a reviewer token for a session cookie; the token never stays in the page. */
export default function SignIn({
  onSignedIn,
}: {
  onSignedIn: (reviewer: string, canStartRuns: boolean) => void;
}) {
  const [token, setToken] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(event: FormEvent) {
    event.preventDefault();
    // HTTPS and this computer are secure contexts; anywhere else the token would be sent
    // in the clear, so never send it.
    if (!window.isSecureContext) {
      setError("Sign-in needs HTTPS. Ask the operator to serve the app behind a TLS proxy.");
      return;
    }
    setBusy(true);
    try {
      const response = await fetch("/api/session", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ token: token.trim() }),
      });
      const body = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(body.detail ?? `Sign-in failed (${response.status})`);
      setToken("");
      onSignedIn(body.reviewer, body.can_start_runs !== false);
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : "Sign-in failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="sign-in">
      <form onSubmit={submit}>
        <span className="eyebrow">WEEDZ · FIELD REVIEW</span>
        <h1>Sign in to review</h1>
        <p>
          Use the reviewer token you were sent. Your records are saved under the name it was issued
          for.
        </p>
        <label htmlFor="reviewer-token">Reviewer token</label>
        <input
          id="reviewer-token"
          type="password"
          value={token}
          onChange={(event) => setToken(event.target.value)}
          autoComplete="off"
          spellCheck={false}
          required
          aria-describedby="token-help"
        />
        <small id="token-help">
          It starts with weedz_. Lost it, or shared it by mistake? Ask the operator to revoke it and
          send a new one.
        </small>
        {error && (
          <div role="alert" className="error-banner">
            {error}
          </div>
        )}
        <button type="submit" className="primary" disabled={busy || !token.trim()}>
          Sign in
        </button>
      </form>
    </main>
  );
}
