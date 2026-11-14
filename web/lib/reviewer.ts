import { useEffect, useState } from "react";

const REVIEWER_KEY = "weedz-reviewer";

/**
 * Who is reviewing: the signed-in reviewer when the API requires tokens, otherwise the
 * name typed on this computer (remembered in this browser). The setter is undefined when
 * the name is fixed by sign-in.
 */
export function useReviewer(signedInAs?: string): [string, ((name: string) => void) | undefined] {
  const [typed, setTyped] = useState("");
  useEffect(() => {
    if (signedInAs) return;
    try {
      setTyped(localStorage.getItem(REVIEWER_KEY) ?? "");
    } catch {
      // Storage can be unavailable; the name is then entered each session.
    }
  }, [signedInAs]);

  function change(name: string) {
    setTyped(name);
    try {
      localStorage.setItem(REVIEWER_KEY, name.trim());
    } catch {
      // Not remembered, but still sent with this session's decisions.
    }
  }
  return signedInAs ? [signedInAs, undefined] : [typed, change];
}
