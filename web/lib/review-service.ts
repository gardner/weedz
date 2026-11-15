/** Runtime boundary shared by local development and the hosted review service. */
export type ReviewEnvironment = Record<string, string | undefined>;

function localAddress(hostname: string): boolean {
  const host = hostname.replace(/^\[|\]$/g, "").toLowerCase();
  if (
    host === "localhost" ||
    host.endsWith(".localhost") ||
    host.endsWith(".local") ||
    host.endsWith(".internal")
  )
    return true;
  if (host === "::" || host === "::1") return true;
  if (host.includes(":")) return /^(fc|fd|fe8|fe9|fea|feb)/.test(host);
  if (!/^\d+\.\d+\.\d+\.\d+$/.test(host)) return !host.includes(".");
  const [first, second] = host.split(".").map(Number);
  return (
    first === 0 ||
    first === 10 ||
    first === 127 ||
    (first === 169 && second === 254) ||
    (first === 172 && second >= 16 && second <= 31) ||
    (first === 192 && second === 168)
  );
}

/** A hosted service must configure its internal or HTTPS API explicitly. */
export function backendOrigin(env: ReviewEnvironment = process.env): string {
  const deployed = env.WEEDZ_DEPLOYMENT === "beast";
  const configured = env.WEEDZ_API_URL;
  if (deployed && !configured) throw new Error("Configure the review API origin.");
  let url: URL;
  try {
    url = new URL(configured || "http://127.0.0.1:8000");
  } catch {
    throw new Error("The review API origin is invalid.");
  }
  if (
    !["http:", "https:"].includes(url.protocol) ||
    url.username ||
    url.password ||
    url.search ||
    url.hash ||
    url.pathname !== "/"
  ) {
    throw new Error("Use a review API origin without credentials, path or query.");
  }
  const host = url.hostname.replace(/^\[|\]$/g, "");
  const loopback = host === "localhost" || host === "::1" || /^127(\.\d{1,3}){3}$/.test(host);
  if (
    deployed &&
    !(url.protocol === "http:" && loopback) &&
    !(url.protocol === "https:" && !localAddress(url.hostname))
  ) {
    throw new Error("Use a loopback HTTP API or public HTTPS API.");
  }
  return url.origin;
}

/** The hosted Next service listens only on loopback behind its trusted tunnel. */
export function sessionOrigin(request: Request) {
  const url = new URL(request.url);
  return {
    host: request.headers.get("host") ?? url.host,
    proto: url.protocol === "https:" ? "https" : request.headers.get("x-forwarded-proto"),
  };
}

/** Review/session responses contain private evidence or authentication state. */
export function privateHeaders(initial?: HeadersInit): Headers {
  const headers = new Headers(initial);
  headers.set("Cache-Control", "private, no-store");
  headers.set("Pragma", "no-cache");
  headers.set("Expires", "0");
  const vary = headers.get("Vary");
  if (vary !== "*" && !vary?.split(",").some((part) => part.trim().toLowerCase() === "cookie")) {
    headers.set("Vary", vary ? `${vary}, Cookie` : "Cookie");
  }
  return headers;
}

export function reviewJson(body: unknown, init: ResponseInit = {}): Response {
  return Response.json(body, { ...init, headers: privateHeaders(init.headers) });
}

export function runCreationEnabled(env: ReviewEnvironment = process.env): boolean {
  return env.WEEDZ_RUN_CREATION !== "disabled";
}

/** Hosted processing is available only when the API confirms its owned worker is healthy. */
export function sessionCanStartRuns(
  backend: unknown,
  env: ReviewEnvironment = process.env,
): boolean {
  return (
    runCreationEnabled(env) &&
    (env.WEEDZ_DEPLOYMENT !== "beast" ||
      (backend !== null &&
        typeof backend === "object" &&
        "can_start_runs" in backend &&
        backend.can_start_runs === true))
  );
}
