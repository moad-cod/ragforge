import {afterEach, describe, expect, it, vi} from "vitest";
import {apiFetch} from "@/lib/api";

describe("apiFetch", () => {
  afterEach(() => vi.restoreAllMocks());

  it("returns typed JSON from the same-origin backend proxy", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      Response.json({project_id: "project-1"}),
    );

    await expect(apiFetch<{project_id: string}>("/projects/project-1")).resolves
      .toEqual({project_id: "project-1"});
    expect(fetch).toHaveBeenCalledWith(
      "/api/backend/projects/project-1",
      expect.objectContaining({cache: "no-store"}),
    );
  });

  it("preserves backend validation messages", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      Response.json(
        {
          detail: [
            {
              msg: "organization_id must be a valid UUID",
            },
          ],
        },
        {status: 422},
      ),
    );

    await expect(apiFetch("/auth/register")).rejects.toEqual(
      expect.objectContaining({
        status: 422,
        message: "organization_id must be a valid UUID",
      }),
    );
  });
});
