import type { NextRequest } from "next/server";
import {
  backendOrigin,
  privateHeaders,
  reviewJson,
  runCreationEnabled,
} from "../../../lib/review-service";
import { bearerFrom, sameOrigin } from "../../../lib/session-cookie";

export const dynamic = "force-dynamic";

async function forward(request: NextRequest, context: { params: Promise<{ path: string[] }> }) {
  const { path } = await context.params;
  if (
    !["runs", "studies"].includes(path[0]) ||
    path.some((part) => !/^[a-zA-Z0-9_-]+$/.test(part))
  ) {
    return reviewJson({ detail: "Unknown endpoint" }, { status: 404 });
  }
  // Writes come only from this app's own pages, never from a form on another site.
  if (request.method === "POST" && !sameOrigin(request)) {
    return reviewJson({ detail: "Cross-site request refused" }, { status: 403 });
  }
  if (
    request.method === "POST" &&
    path.length === 1 &&
    path[0] === "runs" &&
    !runCreationEnabled()
  ) {
    return reviewJson(
      {
        detail:
          "New collections are not enabled on this review service. Existing evidence can be reviewed.",
      },
      { status: 409 },
    );
  }
  try {
    const body = request.method === "POST" ? await request.text() : undefined;
    // A study version carries its whole definition, rationales included.
    if (body && body.length > (path[0] === "studies" ? 200_000 : 10_000)) {
      return reviewJson({ detail: "Request too large" }, { status: 413 });
    }
    // The signed-in reviewer's token, from a cookie page scripts cannot read (#31).
    const authorization = bearerFrom(request.headers.get("cookie"));
    const response = await fetch(`${backendOrigin()}/${path.join("/")}`, {
      method: request.method,
      headers: {
        "Content-Type": "application/json",
        ...(authorization ? { Authorization: authorization } : {}),
      },
      body,
      cache: "no-store",
      // A follow-up package archive is built in full before it is sent; give it longer.
      signal: AbortSignal.timeout(path.at(-1) === "archive" ? 300_000 : 30_000),
    });
    const headers = privateHeaders({
      "Content-Type": response.headers.get("Content-Type") ?? "application/json",
    });
    const disposition = response.headers.get("Content-Disposition");
    if (disposition) headers.set("Content-Disposition", disposition);
    return new Response(response.body, { status: response.status, headers });
  } catch {
    return reviewJson(
      { detail: "The review service is temporarily unavailable. Please try again." },
      { status: 503 },
    );
  }
}

export const GET = forward;
export const POST = forward;
