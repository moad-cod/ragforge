export class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
    public payload?: unknown,
  ) {
    super(message);
  }
}

function errorMessage(payload: unknown, fallback: string): string {
  if (payload && typeof payload === "object" && "detail" in payload) {
    const detail = (payload as { detail: unknown }).detail;
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail)) {
      return detail
        .map((item) =>
          item && typeof item === "object" && "msg" in item
            ? String(item.msg)
            : String(item),
        )
        .join(", ");
    }
  }
  return fallback;
}

export async function apiFetch<T>(
  path: string,
  init: RequestInit = {},
): Promise<T> {
  const headers = new Headers(init.headers);
  if (init.body && !(init.body instanceof FormData) && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  const response = await fetch(`/api/backend${path}`, {
    ...init,
    headers,
    cache: "no-store",
  });

  if (!response.ok) {
    const payload = await response.json().catch(() => null);
    throw new ApiError(
      errorMessage(payload, `Request failed with status ${response.status}`),
      response.status,
      payload,
    );
  }

  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

export async function authFetch<T>(
  path: string,
  body?: unknown,
): Promise<T> {
  const response = await fetch(`/api/auth${path}`, {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  const payload = await response.json().catch(() => null);
  if (!response.ok) {
    throw new ApiError(
      errorMessage(payload, `Request failed with status ${response.status}`),
      response.status,
      payload,
    );
  }
  return payload as T;
}
