import {cookies} from "next/headers";
import {NextRequest} from "next/server";
import {AUTH_COOKIE, backendUrl} from "@/lib/server-auth";

const FORWARDED_REQUEST_HEADERS = [
  "accept",
  "content-type",
  "last-event-id",
];

const FORWARDED_RESPONSE_HEADERS = [
  "cache-control",
  "content-disposition",
  "content-type",
  "x-accel-buffering",
];

async function proxy(
  request: NextRequest,
  context: {params: Promise<{path: string[]}>},
) {
  const {path} = await context.params;
  const cookieStore = await cookies();
  const token = cookieStore.get(AUTH_COOKIE)?.value;
  if (!token) {
    return Response.json({detail: "Not authenticated"}, {status: 401});
  }

  const headers = new Headers();
  for (const name of FORWARDED_REQUEST_HEADERS) {
    const value = request.headers.get(name);
    if (value) headers.set(name, value);
  }
  headers.set("Authorization", `Bearer ${token}`);

  const hasBody = !["GET", "HEAD"].includes(request.method);
  const response = await fetch(
    backendUrl(
      `${
        request.nextUrl.pathname.slice("/api/backend".length) ||
        `/${path.join("/")}`
      }${request.nextUrl.search}`,
    ),
    {
      method: request.method,
      headers,
      body: hasBody ? await request.arrayBuffer() : undefined,
      cache: "no-store",
    },
  );

  const responseHeaders = new Headers();
  for (const name of FORWARDED_RESPONSE_HEADERS) {
    const value = response.headers.get(name);
    if (value) responseHeaders.set(name, value);
  }
  return new Response(response.body, {
    status: response.status,
    statusText: response.statusText,
    headers: responseHeaders,
  });
}

export const GET = proxy;
export const POST = proxy;
export const PATCH = proxy;
export const DELETE = proxy;
