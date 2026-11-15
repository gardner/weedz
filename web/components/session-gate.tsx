"use client";

import { useEffect, useRef, useState } from "react";
import ReviewDesk from "./review-desk";
import SignIn from "./sign-in";

/** Who is reviewing; worker availability can change without changing this identity. */
type Session = { signedInAs?: string; canStartRuns?: boolean } | null;

export default function SessionGate() {
  const [session, setSession] = useState<Session>();
  const version = useRef(0);
  const refreshing = useRef(true);
  useEffect(() => {
    let mounted = true;
    let pending = false;
    async function refresh() {
      if (!refreshing.current || pending) return;
      pending = true;
      const requested = ++version.current;
      const current = () => mounted && refreshing.current && requested === version.current;
      const unavailable = () => {
        if (current())
          setSession((previous) =>
            previous === null ? null : { ...previous, canStartRuns: false },
          );
      };
      try {
        const response = await fetch("/api/session", { cache: "no-store" });
        if (!current()) return;
        if (response.status === 401) {
          refreshing.current = false;
          setSession(null);
          return;
        }
        if (!response.ok) return unavailable();
        const body = await response.json().catch(() => ({}));
        if (!current()) return;
        if (body?.mode === "tokens" && typeof body.reviewer === "string") {
          setSession({ signedInAs: body.reviewer, canStartRuns: body.can_start_runs === true });
        } else if (body?.mode === "local") {
          setSession({ canStartRuns: body.can_start_runs === true });
        } else unavailable();
      } catch {
        unavailable();
      } finally {
        pending = false;
      }
    }
    void refresh();
    const timer = setInterval(() => void refresh(), 5000);
    return () => {
      mounted = false;
      version.current++;
      clearInterval(timer);
    };
  }, []);

  async function signOut() {
    refreshing.current = false;
    version.current++;
    await fetch("/api/session", { method: "DELETE" }).catch(() => undefined);
    setSession(null);
  }

  if (session === undefined) return null;
  if (session === null) {
    return (
      <SignIn
        onSignedIn={(reviewer, canStartRuns) => {
          version.current++;
          refreshing.current = true;
          setSession({ signedInAs: reviewer, canStartRuns });
        }}
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
