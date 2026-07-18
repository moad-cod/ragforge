import {NextResponse} from "next/server";
import {AUTH_COOKIE} from "@/lib/server-auth";

export async function POST() {
  const response = NextResponse.json({authenticated: false});
  response.cookies.set(AUTH_COOKIE, "", {
    httpOnly: true,
    sameSite: "lax",
    path: "/",
    expires: new Date(0),
  });
  return response;
}
