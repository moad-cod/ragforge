import {render, screen, waitFor} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import {beforeEach, describe, expect, it, vi} from "vitest";
import LoginPage from "./page";

const {replace, refresh, toastError} = vi.hoisted(() => ({
  replace: vi.fn(),
  refresh: vi.fn(),
  toastError: vi.fn(),
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({
    replace,
    refresh,
  }),
}));

vi.mock("sonner", () => ({
  toast: {
    error: toastError,
  },
}));

describe("LoginPage", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    replace.mockReset();
    refresh.mockReset();
    toastError.mockReset();
  });

  it("renders the sign-in form and only valid auth links", () => {
    render(<LoginPage />);

    expect(screen.getByRole("heading", {name: "Sign in to RAGForge"}))
      .toBeInTheDocument();
    expect(screen.getByLabelText("Email address")).toBeInTheDocument();
    expect(screen.getByLabelText("Password")).toBeInTheDocument();
    expect(screen.getByRole("button", {name: "Sign in"})).toBeInTheDocument();
    expect(screen.getByRole("link", {name: "Create an account"}))
      .toHaveAttribute("href", "/register");
    expect(screen.queryByRole("link", {name: /forgot password/i})).not
      .toBeInTheDocument();
  });

  it("shows validation messages before submitting", async () => {
    const user = userEvent.setup();
    const fetchMock = vi.spyOn(globalThis, "fetch");

    render(<LoginPage />);

    await user.type(screen.getByLabelText("Email address"), "not-an-email");
    await user.type(screen.getByLabelText("Password"), "short");
    await user.click(screen.getByRole("button", {name: "Sign in"}));

    expect(await screen.findByText("Enter a valid email address"))
      .toBeInTheDocument();
    expect(screen.getByText("Password must be at least 8 characters"))
      .toBeInTheDocument();
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("submits through the existing authentication route", async () => {
    const user = userEvent.setup();
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      Response.json({authenticated: true}),
    );

    render(<LoginPage />);

    await user.type(screen.getByLabelText("Email address"), "user@example.com");
    await user.type(screen.getByLabelText("Password"), "strong-password");
    await user.click(screen.getByRole("button", {name: "Sign in"}));

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        "/api/auth/login",
        expect.objectContaining({
          method: "POST",
          headers: {"Content-Type": "application/json"},
          body: JSON.stringify({
            email: "user@example.com",
            password: "strong-password",
          }),
        }),
      );
      expect(replace).toHaveBeenCalledWith("/projects");
      expect(refresh).toHaveBeenCalled();
    });
  });

  it("keeps the submit button disabled while authentication is pending", async () => {
    const user = userEvent.setup();
    let resolveLogin: (value: Response) => void = () => undefined;
    vi.spyOn(globalThis, "fetch").mockReturnValue(
      new Promise<Response>((resolve) => {
        resolveLogin = resolve;
      }),
    );

    render(<LoginPage />);

    await user.type(screen.getByLabelText("Email address"), "user@example.com");
    await user.type(screen.getByLabelText("Password"), "strong-password");
    await user.click(screen.getByRole("button", {name: "Sign in"}));

    await waitFor(() => {
      expect(screen.getByRole("button", {name: "Sign in"})).toBeDisabled();
    });

    resolveLogin(Response.json({authenticated: true}));

    await waitFor(() => {
      expect(replace).toHaveBeenCalledWith("/projects");
    });
  });

  it("announces backend authentication failures near the form", async () => {
    const user = userEvent.setup();
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      Response.json({detail: "Invalid credentials"}, {status: 401}),
    );

    render(<LoginPage />);

    await user.type(screen.getByLabelText("Email address"), "user@example.com");
    await user.type(screen.getByLabelText("Password"), "wrong-password");
    await user.click(screen.getByRole("button", {name: "Sign in"}));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Invalid credentials",
    );
    expect(toastError).toHaveBeenCalledWith("Invalid credentials");
    expect(replace).not.toHaveBeenCalled();
  });

  it("toggles password visibility with an accessible control", async () => {
    const user = userEvent.setup();
    render(<LoginPage />);

    const password = screen.getByLabelText("Password") as HTMLInputElement;

    expect(password.type).toBe("password");
    await user.click(screen.getByRole("button", {name: "Show password"}));
    expect(password.type).toBe("text");
    await user.click(screen.getByRole("button", {name: "Hide password"}));
    expect(password.type).toBe("password");
  });
});
