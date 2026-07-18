import {NextResponse} from "next/server";
import {backendUrl} from "@/lib/server-auth";

export async function POST(request: Request) {
  const body = await request.text();
  const response = await fetch(backendUrl("/auth/register"), {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body,
    cache: "no-store",
  });
  const payload = await response.json().catch(() => ({
    detail: "Registration service returned an invalid response",
  }));
  return NextResponse.json(payload, {status: response.status});
}
