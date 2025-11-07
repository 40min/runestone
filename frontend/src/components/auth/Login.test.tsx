import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi } from "vitest";
import Login from "./Login";
import { AuthProvider } from "../../context/AuthContext";

// Mock config
vi.mock("../../config", () => ({
  API_BASE_URL: "http://localhost:8010",
}));

// Mock fetch
global.fetch = vi.fn();

describe("Login", () => {
  const mockOnSwitchToRegister = vi.fn();

  const wrapper = ({ children }: { children: React.ReactNode }) => (
    <AuthProvider>{children}</AuthProvider>
  );

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders login form", () => {
    render(<Login onSwitchToRegister={mockOnSwitchToRegister} />, { wrapper });

    expect(screen.getByRole("heading", { name: "Login" })).toBeInTheDocument();
    expect(screen.getByLabelText(/^Email\s+\*\s*$/)).toBeInTheDocument();
    expect(screen.getByLabelText(/^Password\s+\*\s*$/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Login" })).toBeInTheDocument();
    expect(
      screen.getByText("Don't have an account? Register")
    ).toBeInTheDocument();
  });

  it("handles successful login", async () => {
    const mockTokenResponse = { access_token: "test-token" };
    const mockUserResponse = {
      id: 1,
      email: "test@example.com",
      name: "Test",
      surname: "User",
      timezone: "UTC",
      pages_recognised_count: 5,
    };

    vi.mocked(global.fetch)
      .mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockTokenResponse),
      } as Response)
      .mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockUserResponse),
      } as Response);

    render(<Login onSwitchToRegister={mockOnSwitchToRegister} />, { wrapper });

    const emailInput = screen.getByLabelText(/^Email\s+\*\s*$/);
    const passwordInput = screen.getByLabelText(/^Password\s+\*\s*$/);
    const loginButton = screen.getByRole("button", { name: "Login" });

    await userEvent.type(emailInput, "test@example.com");
    await userEvent.type(passwordInput, "password123");
    await userEvent.click(loginButton);

    await waitFor(() => {
      // Check first call - authentication request
      expect(global.fetch).toHaveBeenNthCalledWith(
        1,
        "http://localhost:8010/api/auth/",
        expect.objectContaining({
          method: "POST",
          body: JSON.stringify({
            email: "test@example.com",
            password: "password123",
          }),
        })
      );

      // Check second call - user data request with token (now properly authenticated!)
      expect(global.fetch).toHaveBeenNthCalledWith(
        2,
        "http://localhost:8010/api/me",
        {
          method: "GET",
          headers: {
            "Authorization": "Bearer test-token",
            "Content-Type": "application/json",
          },
        }
      );
    });

    expect(screen.queryByText("Logging in...")).not.toBeInTheDocument();
  });

  it("handles login failure", async () => {
    vi.mocked(global.fetch).mockResolvedValueOnce({
      ok: false,
      json: () => Promise.resolve({ detail: "Invalid credentials" }),
    } as Response);

    render(<Login onSwitchToRegister={mockOnSwitchToRegister} />, { wrapper });

    const emailInput = screen.getByLabelText(/^Email\s+\*\s*$/);
    const passwordInput = screen.getByLabelText(/^Password\s+\*\s*$/);
    const loginButton = screen.getByRole("button", { name: "Login" });

    await userEvent.type(emailInput, "test@example.com");
    await userEvent.type(passwordInput, "wrongpassword");
    await userEvent.click(loginButton);

    await waitFor(() => {
      expect(screen.getByText("Invalid credentials")).toBeInTheDocument();
    });
  });

  it("shows loading state during login", async () => {
    vi.mocked(global.fetch).mockImplementation(
      () =>
        new Promise((resolve) =>
          setTimeout(
            () =>
              resolve({
                ok: true,
                json: () => Promise.resolve({ access_token: "token" }),
              } as Response),
            100
          )
        )
    );

    render(<Login onSwitchToRegister={mockOnSwitchToRegister} />, { wrapper });

    const emailInput = screen.getByLabelText(/^Email\s+\*\s*$/);
    const passwordInput = screen.getByLabelText(/^Password\s+\*\s*$/);
    const loginButton = screen.getByRole("button", { name: "Login" });

    await userEvent.type(emailInput, "test@example.com");
    await userEvent.type(passwordInput, "password123");
    await userEvent.click(loginButton);

    // Verify loading state appears
    expect(screen.getByText("Logging in...")).toBeInTheDocument();
    const loadingButton = screen.getByRole("button", { name: /logging in/i });
    expect(loadingButton).toBeDisabled();

    // Verify loading state clears
    await waitFor(() => {
      expect(screen.queryByText("Logging in...")).not.toBeInTheDocument();
    });

    const normalButton = screen.getByRole("button", { name: "Login" });
    expect(normalButton).not.toBeDisabled();
  });

  it("clears previous errors when new operation starts", async () => {
    // First show an error
    vi.mocked(global.fetch).mockRejectedValueOnce(new Error("First error"));

    render(<Login onSwitchToRegister={mockOnSwitchToRegister} />, { wrapper });

    const emailInput = screen.getByLabelText(/^Email\s+\*\s*$/);
    const passwordInput = screen.getByLabelText(/^Password\s+\*\s*$/);
    const loginButton = screen.getByRole("button", { name: "Login" });

    await userEvent.type(emailInput, "test@example.com");
    await userEvent.type(passwordInput, "password123");
    await userEvent.click(loginButton);

    await waitFor(() => {
      expect(screen.getByText("First error")).toBeInTheDocument();
    });

    // Now succeed - error should clear
    vi.mocked(global.fetch)
      .mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({ access_token: "token" }),
      } as Response)
      .mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({ id: 1, email: "test@example.com" }),
      } as Response);

    await userEvent.click(loginButton);

    await waitFor(() => {
      expect(screen.queryByText("First error")).not.toBeInTheDocument();
    });
  });

  it("calls onSwitchToRegister when register link is clicked", async () => {
    render(<Login onSwitchToRegister={mockOnSwitchToRegister} />, { wrapper });

    const registerLink = screen.getByText("Don't have an account? Register");
    await userEvent.click(registerLink);

    expect(mockOnSwitchToRegister).toHaveBeenCalledTimes(1);
  });

  it("has submit button", async () => {
    render(<Login onSwitchToRegister={mockOnSwitchToRegister} />, { wrapper });

    const loginButton = screen.getByRole("button", { name: "Login" });

    // Button should be of type submit to submit the form
    expect(loginButton).toHaveAttribute("type", "submit");
  });

  it("requires email and password fields", () => {
    render(<Login onSwitchToRegister={mockOnSwitchToRegister} />, { wrapper });

    const emailInput = screen.getByLabelText(/^Email\s+\*\s*$/);
    const passwordInput = screen.getByLabelText(/^Password\s+\*\s*$/);

    expect(emailInput).toBeRequired();
    expect(passwordInput).toBeRequired();
  });

  it("does not validate empty email field (server-side validation)", async () => {
    vi.mocked(global.fetch).mockResolvedValueOnce({
      ok: false,
      json: () => Promise.resolve({ detail: "Email is required" }),
    } as Response);

    render(<Login onSwitchToRegister={mockOnSwitchToRegister} />, { wrapper });

    const passwordInput = screen.getByLabelText(/^Password\s+\*\s*$/);
    const loginButton = screen.getByRole("button", { name: "Login" });

    // Leave email empty and try to login
    await userEvent.type(passwordInput, "password123");
    await userEvent.click(loginButton);

    // Should attempt login and get server-side validation error
    await waitFor(() => {
      expect(global.fetch).toHaveBeenCalled();
    });

    // Component shows error from server
    expect(screen.getByText("Email is required")).toBeInTheDocument();
  });

  it("does not validate email format (server-side validation)", async () => {
    vi.mocked(global.fetch).mockResolvedValueOnce({
      ok: false,
      json: () => Promise.resolve({ detail: "Invalid email format" }),
    } as Response);

    render(<Login onSwitchToRegister={mockOnSwitchToRegister} />, { wrapper });

    const emailInput = screen.getByLabelText(/^Email\s+\*\s*$/);
    const passwordInput = screen.getByLabelText(/^Password\s+\*\s*$/);
    const loginButton = screen.getByRole("button", { name: "Login" });

    await userEvent.type(emailInput, "invalid-email-format");
    await userEvent.type(passwordInput, "password123");
    await userEvent.click(loginButton);

    // Should attempt login and get server-side validation error
    await waitFor(() => {
      expect(global.fetch).toHaveBeenCalled();
    });

    // Component shows error from server
    expect(screen.getByText("Invalid email format")).toBeInTheDocument();
  });

  it("handles network timeout gracefully", async () => {
    vi.mocked(global.fetch).mockImplementation(
      () =>
        new Promise((_, reject) =>
          setTimeout(() => reject(new Error("Request timeout")), 100)
        )
    );

    render(<Login onSwitchToRegister={mockOnSwitchToRegister} />, { wrapper });

    const emailInput = screen.getByLabelText(/^Email\s+\*\s*$/);
    const passwordInput = screen.getByLabelText(/^Password\s+\*\s*$/);
    const loginButton = screen.getByRole("button", { name: "Login" });

    await userEvent.type(emailInput, "test@example.com");
    await userEvent.type(passwordInput, "password123");
    await userEvent.click(loginButton);

    await waitFor(
      () => {
        expect(screen.getByText(/timeout|timed out/i)).toBeInTheDocument();
      },
      { timeout: 2000 }
    );
  });
});
