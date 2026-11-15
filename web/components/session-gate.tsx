"use client";

import { useEffect, useState } from "react";
import ReviewDesk from "./review-desk";
import SignIn from "./sign-in";

/** Who is reviewing: `signedInAs` when the API requires tokens; null until signed in. */
type Session = { signedInAs?: string; canStartRuns?: boolean } | null;

/**
 * Show the review desk to whoever the API accepts. Only a 401 asks for sign-in; any other
 * answer opens the desk, which reports its own errors (issue #31).
 */
export default function SessionGate() {
  const [session, setSession] = useState<Session>();
  useEffect(() => {
    fetch("/api/session", { cache: "no-store" })
      .then(async (response): Promise<Session> => {
        if (response.status === 401) return null;
        const body = await response.json().catch(() => ({}));
        const signedIn = body.mode === "tokens" && typeof body.reviewer === "string";
        return signedIn
          ? { signedInAs: body.reviewer, canStartRuns: body.can_start_runs !== false }
          : { canStartRuns: body.can_start_runs !== false };
      })
      .catch(() => ({}))
      .then(setSession);
  }, []);

  async function signOut() {
    await fetch("/api/session", { method: "DELETE" }).catch(() => undefined);
    setSession(null);
  }

  if (session === undefined) return null;
  if (session === null) {
    return (
      <SignIn
        onSignedIn={(reviewer, canStartRuns) => setSession({ signedInAs: reviewer, canStartRuns })}
      />
    );
  }
  return session.signedInAs ? (
    <ReviewDesk
      canStartRuns={session.canStartRuns}
      signedInAs={session.signedInAs}
      onSignOut={signOut}
    />
  ) : (
    <ReviewDesk canStartRuns={session.canStartRuns} />
  );
}
