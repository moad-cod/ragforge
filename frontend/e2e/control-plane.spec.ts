import {expect, test, type Page} from "@playwright/test";

const user = {
  user_id: "10000000-0000-0000-0000-000000000001",
  organization_id: null,
  email: "user@example.com",
  full_name: "RAGForge User",
  created_at: "2026-07-16T00:00:00Z",
  updated_at: "2026-07-16T00:00:00Z",
};

async function authenticate(page: Page) {
  await page.context().addCookies([
    {
      name: "ragforge_session",
      value: "test-token",
      url: "http://127.0.0.1:3100",
      httpOnly: true,
      sameSite: "Lax",
    },
  ]);
  await page.route("**/api/auth/login", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({authenticated: true}),
    }),
  );
  await page.route("**/api/backend/auth/me", (route) =>
    route.fulfill({status: 200, json: user}),
  );
  await page.goto("/login");
  await page.getByLabel("Email address").fill("user@example.com");
  await page.getByLabel("Password").fill("strong-password");
}

test("shows the authenticated empty workspace state", async ({page}) => {
  await authenticate(page);
  await page.route("**/api/backend/projects/", (route) =>
    route.fulfill({status: 200, json: []}),
  );

  await page.getByRole("button", {name: "Sign in"}).click();

  await expect(page).toHaveURL(/\/projects$/);
  await expect(page.getByText("No projects yet")).toBeVisible();
  await expect(page.getByRole("button", {name: "Create project"})).toBeVisible();
});

test("renders a project returned by the control-plane API", async ({page}) => {
  await authenticate(page);
  await page.route("**/api/backend/projects/", (route) =>
    route.fulfill({
      status: 200,
      json: [
        {
          project_id: "20000000-0000-0000-0000-000000000001",
          organization_id: null,
          name: "Product knowledge",
          collection: "project_20000000",
          qdrant_collection: "project_20000000",
          created_by: user.user_id,
          created_at: "2026-07-16T00:00:00Z",
          updated_at: "2026-07-16T00:00:00Z",
        },
      ],
    }),
  );

  await page.getByRole("button", {name: "Sign in"}).click();

  await expect(page.getByText("Product knowledge")).toBeVisible();
  await expect(page.getByRole("link", {name: "Open workspace"})).toHaveAttribute(
    "href",
    "/projects/20000000-0000-0000-0000-000000000001/documents",
  );
});

test("surfaces backend authentication failures", async ({page}) => {
  await page.route("**/api/auth/login", (route) =>
    route.fulfill({
      status: 401,
      contentType: "application/json",
      body: JSON.stringify({detail: "Invalid credentials"}),
    }),
  );
  await page.goto("/login");
  await page.getByLabel("Email address").fill("user@example.com");
  await page.getByLabel("Password").fill("wrong-password");

  await page.getByRole("button", {name: "Sign in"}).click();

  await expect(page.getByText("Invalid credentials")).toBeVisible();
  await expect(page).toHaveURL(/\/login$/);
});
