const BACKEND = process.env.BACKEND_URL ?? "http://localhost:8000";

async function proxy(req: Request, params: Promise<{ path: string[] }>) {
  const { path } = await params;
  const url = `${BACKEND}/api/${path.join("/")}`;
  const headers = new Headers(req.headers);
  for (const h of ["host", "connection", "content-length"]) headers.delete(h);
  const clientIp = req.headers.get("x-real-ip") ?? req.headers.get("x-forwarded-for")?.split(",")[0]?.trim();
  headers.delete("x-client-ip");
  if (clientIp) headers.set("x-client-ip", clientIp);
  if (process.env.API_SECRET) headers.set("x-finch-key", process.env.API_SECRET);
  const res = await fetch(url, {
    method: req.method,
    headers,
    body: req.method === "GET" ? undefined : req.body,
    // @ts-expect-error duplex is required to stream a request body
    duplex: "half",
    cache: "no-store",
  });
  return new Response(res.body, { status: res.status, headers: res.headers });
}

export async function GET(req: Request, ctx: { params: Promise<{ path: string[] }> }) {
  return proxy(req, ctx.params);
}

export async function POST(req: Request, ctx: { params: Promise<{ path: string[] }> }) {
  return proxy(req, ctx.params);
}
