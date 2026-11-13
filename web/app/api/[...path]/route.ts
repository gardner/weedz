import type { NextRequest } from "next/server";

export const dynamic = "force-dynamic";
const backend = process.env.WEEDZ_API_URL ?? "http://127.0.0.1:8000";

async function forward(request: NextRequest, context: { params: Promise<{ path: string[] }> }) {
  const { path } = await context.params;
  if (path[0] !== "runs" || path.some((part) => !/^[a-zA-Z0-9_-]+$/.test(part))) {
    return Response.json({ detail: "Unknown endpoint" }, { status: 404 });
  }
  try {
    const body = request.method === "POST" ? await request.text() : undefined;
    if (body && body.length > 10_000) {
      return Response.json({ detail: "Request too large" }, { status: 413 });
    }
    const response = await fetch(`${backend}/${path.join("/")}`, {
      method: request.method,
      headers: { "Content-Type": "application/json" },
      body,
      cache: "no-store",
      signal: AbortSignal.timeout(30_000),
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
