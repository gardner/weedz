import type { NextRequest } from "next/server";

export const dynamic = "force-dynamic";
const backend = process.env.WEEDZ_API_URL ?? "http://127.0.0.1:8000";

async function forward(request: NextRequest, context: { params: Promise<{ path: string[] }> }) {
  const { path } = await context.params;
  if (
    !["runs", "studies"].includes(path[0]) ||
    path.some((part) => !/^[a-zA-Z0-9_-]+$/.test(part))
  ) {
    return Response.json({ detail: "Unknown endpoint" }, { status: 404 });
  }
  try {
    const body = request.method === "POST" ? await request.text() : undefined;
    // A study version carries its whole definition, rationales included.
    if (body && body.length > (path[0] === "studies" ? 200_000 : 10_000)) {
      return Response.json({ detail: "Request too large" }, { status: 413 });
    }
    const response = await fetch(`${backend}/${path.join("/")}`, {
      method: request.method,
      headers: { "Content-Type": "application/json" },
      body,
      cache: "no-store",
      // A follow-up package archive is built in full before it is sent; give it longer.
      signal: AbortSignal.timeout(path.at(-1) === "archive" ? 300_000 : 30_000),
    });
    const headers = new Headers({
      "Content-Type": response.headers.get("Content-Type") ?? "application/json",
    });
    const disposition = response.headers.get("Content-Disposition");
    if (disposition) headers.set("Content-Disposition", disposition);
    return new Response(response.body, { status: response.status, headers });
  } catch {
    return Response.json(
      { detail: "The Python service is unavailable. Start uv run main.py dev." },
      { status: 503 },
    );
  }
}

export const GET = forward;
export const POST = forward;
