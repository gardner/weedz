/**
 * The signed-in reviewer's token, kept in a cookie page scripts cannot read (issue #31).
 * Pure functions with no imports, so the Node checks can load them directly.
 */
export const SESSION_COOKIE = "weedz_session";
const MAX_AGE = 30 * 24 * 60 * 60;
// The shape `main.py reviewers add` issues: nothing that could break out of a header.
const TOKEN = /^weedz_\d{1,12}_[A-Za-z0-9_-]{1,128}$/;

/** Where the request came from: its Host header and any proxy's X-Forwarded-Proto. */
export type Origin = { host: string; proto?: string | null };

export function validToken(token: string): boolean {
  return TOKEN.test(token);
}

export function isLoopback(host: string): boolean {
  const name = host.startsWith("[")
    ? host.slice(1, host.indexOf("]"))
    : host.includes(":") && host.indexOf(":") === host.lastIndexOf(":")
      ? host.slice(0, host.indexOf(":"))
      : host;
  return name === "localhost" || name === "::1" || /^127(\.\d{1,3}){3}$/.test(name);
}

/** HTTPS, or a request that never left this computer: safe to carry a token. */
export function privateTransport(origin: Origin): boolean {
  return origin.proto === "https" || isLoopback(origin.host);
}

/** Secure everywhere but plain http on this computer, where a browser would drop it. */
function attributes(origin: Origin, maxAge: number): string {
  const secure = origin.proto === "https" || !isLoopback(origin.host);
  return `Path=/; Max-Age=${maxAge}; HttpOnly; SameSite=Strict${secure ? "; Secure" : ""}`;
}

export function sessionCookie(token: string, origin: Origin): string {
  if (!validToken(token)) throw new Error("Not a reviewer token");
  return `${SESSION_COOKIE}=${token}; ${attributes(origin, MAX_AGE)}`;
}

export function clearedCookie(origin: Origin): string {
  return `${SESSION_COOKIE}=; ${attributes(origin, 0)}`;
}

/** False for a request a browser says another site started (Fetch Metadata). */
export function sameOrigin(request: { headers: { get(name: string): string | null } }): boolean {
  const site = request.headers.get("sec-fetch-site");
  return site === null || site === "same-origin" || site === "none";
}

/** The Authorization header for the API, from a request's Cookie header. */
export function bearerFrom(cookies: string | null): string | undefined {
  for (const part of cookies?.split(";") ?? []) {
    const [name, ...value] = part.trim().split("=");
    const token = value.join("=");
    if (name === SESSION_COOKIE && validToken(token)) return `Bearer ${token}`;
  }
  return undefined;
}
