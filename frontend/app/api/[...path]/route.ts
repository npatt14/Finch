const BACKEND = process.env.BACKEND_URL ?? "http://localhost:8000";

async function proxy(req: Request, params: Promise<{ path: string[] }>) {
  const { path } = await params;
  const url = `${BACKEND}/api/${path.join("/")}`;
  const res = await fetch(url, {
    method: req.method,
    headers: req.headers,
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
