import {QueryClient, QueryClientProvider} from "@tanstack/react-query";
import {render, screen} from "@testing-library/react";
import {beforeEach, describe, expect, it, vi} from "vitest";
import ProjectsPage from "@/app/(dashboard)/projects/page";
import {apiFetch} from "@/lib/api";

vi.mock("@/lib/api", () => ({
  apiFetch: vi.fn(),
}));

function renderPage() {
  const client = new QueryClient({
    defaultOptions: {queries: {retry: false}},
  });
  return render(
    <QueryClientProvider client={client}>
      <ProjectsPage />
    </QueryClientProvider>,
  );
}

describe("ProjectsPage", () => {
  beforeEach(() => vi.mocked(apiFetch).mockReset());

  it("renders a loading state while projects are unresolved", async () => {
    let resolveProjects!: (value: never[]) => void;
    vi.mocked(apiFetch).mockReturnValue(
      new Promise((resolve) => {
        resolveProjects = resolve;
      }),
    );

    renderPage();

    expect(screen.getByLabelText("Loading projects")).toBeInTheDocument();
    resolveProjects([]);
    expect(await screen.findByText("No projects yet")).toBeInTheDocument();
  });

  it("renders the empty workspace state", async () => {
    vi.mocked(apiFetch).mockResolvedValue([]);

    renderPage();

    expect(await screen.findByText("No projects yet")).toBeInTheDocument();
    expect(
      screen.getByRole("button", {name: "Create project"}),
    ).toBeInTheDocument();
  });

  it("renders a successful project result", async () => {
    vi.mocked(apiFetch).mockResolvedValue([
      {
        project_id: "project-1",
        organization_id: null,
        name: "Product knowledge",
        collection: "project_project-1",
        qdrant_collection: "project_project-1",
        created_by: "user-1",
        created_at: "2026-07-16T00:00:00Z",
        updated_at: "2026-07-16T00:00:00Z",
      },
    ]);

    renderPage();

    expect(await screen.findByText("Product knowledge")).toBeInTheDocument();
    expect(screen.getByRole("link", {name: /open workspace/i})).toHaveAttribute(
      "href",
      "/projects/project-1/documents",
    );
  });
});
