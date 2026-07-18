export const AUTH_COOKIE = "ragforge_session";

export function backendUrl(path: string) {
  const base = process.env.BACKEND_URL ?? "http://localhost:8000";
  return `${base.replace(/\/$/, "")}${path}`;
}
