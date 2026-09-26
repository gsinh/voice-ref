// Liveness for the web container itself. Does not check the backends.
export const dynamic = "force-dynamic";

export function GET() {
  return Response.json({ status: "ok" });
}
