import {NextResponse} from "next/server";
import {AUTH_COOKIE, backendUrl} from "@/lib/server-auth";

export async function POST(request: Request) {
  const body = (await request.json()) as {email?: string; password?: string};
  const form = new URLSearchParams({
    username: body.email ?? "",
    password: body.password ?? "",
  });
  const response = await fetch(backendUrl("/auth/login"), {
    method: "POST",
    headers: {"Content-Type": "application/x-www-form-urlencoded"},
    body: form,
    cache: "no-store",
  });
  const payload = await response.json().catch(() => ({
    detail: "Authentication service returned an invalid response",
  }));
  if (!response.ok) {
    return NextResponse.json(payload, {status: response.status});
  }

  const result = NextResponse.json({authenticated: true});
  result.cookies.set(AUTH_COOKIE, String(payload.access_token), {
    httpOnly: true,
    secure: process.env.AUTH_COOKIE_SECURE === "true",
    sameSite: "lax",
    path: "/",
    maxAge: 60 * 60 * 24 * 7,
  });
  return result;
}
