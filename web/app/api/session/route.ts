import type { NextRequest } from "next/server";
import {
  bearerFrom,
  clearedCookie,
  privateTransport,
  sameOrigin,
  sessionCookie,
  validToken,
} from "../../../lib/session-cookie";

export const dynamic = "force-dynamic";
const backend = process.env.WEEDZ_API_URL ?? "http://127.0.0.1:8000";
const unavailable = { detail: "The Python service is unavailable. Start uv run main.py dev." };

function origin(request: NextRequest) {
  return {
    host: request.headers.get("host") ?? "",
    proto: request.headers.get("x-forwarded-proto"),
  };
}

/** Ask the API who a bearer token names; it answers 401 when tokens are required. */
async function session(authorization: string | undefined) {
  return fetch(`${backend}/session`, {
    headers: authorization ? { Authorization: authorization } : {},
    cache: "no-store",
    signal: AbortSignal.timeout(10_000),
  });
}

/** How the API is run and who is signed in. */
export async function GET(request: NextRequest) {
  try {
    const response = await session(bearerFrom(request.headers.get("cookie")));
    return Response.json(await response.json(), { status: response.status });
  } catch {
    return Response.json(unavailable, { status: 503 });
  }
}

/** Sign in: keep a token the API accepts in an HttpOnly cookie; never echo it back. */
export async function POST(request: NextRequest) {
  // Only this app's own script may sign in, so another site cannot sign a browser in as
  // someone else: a cross-site form cannot send JSON, and browsers mark where it came from.
  if (
    !sameOrigin(request) ||
    !request.headers.get("content-type")?.startsWith("application/json")
  ) {
    return Response.json({ detail: "Sign in from the review app" }, { status: 403 });
  }
  // The browser would drop the Secure cookie anyway; say why rather than half sign in.
  if (!privateTransport(origin(request))) {
    return Response.json(
      { detail: "Sign-in needs HTTPS. Ask the operator to serve the app behind a TLS proxy." },
      { status: 400 },
    );
  }
  const { token } = await request.json().catch(() => ({}));
  const presented = typeof token === "string" ? token.trim() : "";
  const refused = Response.json(
    { detail: "That token is not valid or has been revoked." },
    { status: 401 },
  );
  if (!validToken(presented)) return refused;
  try {
    const response = await session(`Bearer ${presented}`);
    const body = await response.json();
    if (!response.ok || body.mode !== "tokens") return refused;
    return Response.json(body, {
      headers: { "Set-Cookie": sessionCookie(presented, origin(request)) },
    });
  } catch {
    return Response.json(unavailable, { status: 503 });
  }
}

/** Sign out of this browser. Revoking the token itself is done with the CLI. */
export function DELETE(request: NextRequest) {
  return Response.json(
    { signed_out: true },
    { headers: { "Set-Cookie": clearedCookie(origin(request)) } },
  );
}
