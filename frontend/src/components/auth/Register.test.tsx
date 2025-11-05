import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi, describe, expect, beforeEach } from "vitest";
import Register from "./Register";
import { AuthProvider } from "../../context/AuthContext";

// Mock fetch
global.fetch = vi.fn();

describe("Register", () => {
  const mockOnSwitchToLogin = vi.fn();

  const wrapper = ({ children }: { children: React.ReactNode }) => (
    <AuthProvider>{children}</AuthProvider>
  );

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders registration form", () => {
    render(<Register onSwitchToLogin={mockOnSwitchToLogin} />, { wrapper });

    expect(screen.getByText("Register")).toBeInTheDocument();
    expect(screen.getByLabelText("Email *")).toBeInTheDocument();
    expect(
      screen.getByLabelText("Password (min. 6 characters) *")
    ).toBeInTheDocument();
    expect(screen.getByLabelText("Confirm Password *")).toBeInTheDocument();
    expect(screen.getByLabelText("Name (optional)")).toBeInTheDocument();
    expect(screen.getByLabelText("Surname (optional)")).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Register" })
    ).toBeInTheDocument();
    expect(
      screen.getByText("Already have an account? Login")
    ).toBeInTheDocument();
  });

  it("handles successful registration", async () => {
    const mockRegisterResponse = { success: true };
    const mockTokenResponse = { access_token: "test-token" };
    const mockUserResponse = {
      id: 1,
      email: "new@example.com",
      name: "New",
      surname: "User",
      timezone: "UTC",
      pages_recognised_count: 0,
    };

    (global.fetch as any)
      .mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockRegisterResponse),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockTokenResponse),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockUserResponse),
      });

    render(<Register onSwitchToLogin={mockOnSwitchToLogin} />, { wrapper });

    const emailInput = screen.getByLabelText("Email *");
    const passwordInput = screen.getByLabelText("Password (min. 6 characters) *");
    const confirmPasswordInput = screen.getByLabelText("Confirm Password *");
    const nameInput = screen.getByLabelText("Name (optional)");
    const surnameInput = screen.getByLabelText("Surname (optional)");
    const registerButton = screen.getByRole("button", { name: "Register" });

    await userEvent.type(emailInput, "new@example.com");
    await userEvent.type(passwordInput, "password123");
    await userEvent.type(confirmPasswordInput, "password123");
    await userEvent.type(nameInput, "New");
    await userEvent.type(surnameInput, "User");
    await userEvent.click(registerButton);

    await waitFor(() => {
      expect(global.fetch).toHaveBeenCalledWith(
        "http://localhost:8000/auth/register",
        expect.objectContaining({
          method: "POST",
          body: JSON.stringify({
            email: "new@example.com",
            password: "password123",
            name: "New",
            surname: "User",
          }),
        })
      );
    });

    expect(screen.queryByText("Registering...")).not.toBeInTheDocument();
  });

  it("validates password mismatch", async () => {
    render(<Register onSwitchToLogin={mockOnSwitchToLogin} />, { wrapper });

    const emailInput = screen.getByLabelText("Email *");
    const passwordInput = screen.getByLabelText("Password (min. 6 characters) *");
    const confirmPasswordInput = screen.getByLabelText("Confirm Password *");
    const registerButton = screen.getByRole("button", { name: "Register" });

    await userEvent.type(emailInput, "test@example.com");
    await userEvent.type(passwordInput, "password123");
    await userEvent.type(confirmPasswordInput, "different123");
    await userEvent.click(registerButton);

    expect(screen.getByText("Passwords do not match")).toBeInTheDocument();
    expect(global.fetch).not.toHaveBeenCalled();
  });

  it("validates password length", async () => {
    render(<Register onSwitchToLogin={mockOnSwitchToLogin} />, { wrapper });

    const emailInput = screen.getByLabelText("Email *");
    const passwordInput = screen.getByLabelText("Password (min. 6 characters) *");
    const confirmPasswordInput = screen.getByLabelText("Confirm Password *");
    const registerButton = screen.getByRole("button", { name: "Register" });

    await userEvent.type(emailInput, "test@example.com");
    await userEvent.type(passwordInput, "12345"); // Less than 6 characters
    await userEvent.type(confirmPasswordInput, "12345");
    await userEvent.click(registerButton);

    expect(
      screen.getByText("Password must be at least 6 characters")
    ).toBeInTheDocument();
    expect(global.fetch).not.toHaveBeenCalled();
  });

  it("auto-logs in after successful registration", async () => {
    const mockRegisterResponse = { success: true };
    const mockTokenResponse = { access_token: "registration-token" };
    const mockUserResponse = {
      id: 1,
      email: "auto@example.com",
      name: "Auto",
      surname: "Login",
      timezone: "UTC",
      pages_recognised_count: 0,
    };

    (global.fetch as any)
      .mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockRegisterResponse),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockTokenResponse),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockUserResponse),
      });

    render(<Register onSwitchToLogin={mockOnSwitchToLogin} />, { wrapper });

    const emailInput = screen.getByLabelText("Email *");
    const passwordInput = screen.getByLabelText("Password (min. 6 characters) *");
    const confirmPasswordInput = screen.getByLabelText("Confirm Password *");
    const registerButton = screen.getByRole("button", { name: "Register" });

    await userEvent.type(emailInput, "auto@example.com");
    await userEvent.type(passwordInput, "password123");
    await userEvent.type(confirmPasswordInput, "password123");
    await userEvent.click(registerButton);

    await waitFor(() => {
      expect(global.fetch).toHaveBeenCalledWith(
        "http://localhost:8000/auth/token",
        expect.objectContaining({
          body: JSON.stringify({
            email: "auto@example.com",
            password: "password123",
          }),
        })
      );
    });
  });

  it("shows loading state during registration", async () => {
    (global.fetch as any).mockImplementation(
      () =>
        new Promise((resolve) =>
          setTimeout(
            () =>
              resolve({
                ok: true,
                json: () => Promise.resolve({ success: true }),
              }),
            100
          )
        )
    );

    render(<Register onSwitchToLogin={mockOnSwitchToLogin} />, { wrapper });

    const emailInput = screen.getByLabelText("Email *");
    const passwordInput = screen.getByLabelText("Password (min. 6 characters) *");
    const confirmPasswordInput = screen.getByLabelText("Confirm Password *");
    const registerButton = screen.getByRole("button", { name: "Register" });

    await userEvent.type(emailInput, "test@example.com");
    await userEvent.type(passwordInput, "password123");
    await userEvent.type(confirmPasswordInput, "password123");
    await userEvent.click(registerButton);

    expect(screen.getByText("Registering...")).toBeInTheDocument();

    await waitFor(() => {
      expect(screen.queryByText("Registering...")).not.toBeInTheDocument();
    });
  });

  it("displays error messages", async () => {
    (global.fetch as any).mockResolvedValueOnce({
      ok: false,
      json: () => Promise.resolve({ detail: "Email already exists" }),
    });

    render(<Register onSwitchToLogin={mockOnSwitchToLogin} />, { wrapper });

    const emailInput = screen.getByLabelText("Email *");
    const passwordInput = screen.getByLabelText("Password (min. 6 characters) *");
    const confirmPasswordInput = screen.getByLabelText("Confirm Password *");
    const registerButton = screen.getByRole("button", { name: "Register" });

    await userEvent.type(emailInput, "existing@example.com");
    await userEvent.type(passwordInput, "password123");
    await userEvent.type(confirmPasswordInput, "password123");
    await userEvent.click(registerButton);

    await waitFor(() => {
      expect(screen.getByText("Email already exists")).toBeInTheDocument();
    });
  });

  it("calls onSwitchToLogin when login link is clicked", async () => {
    render(<Register onSwitchToLogin={mockOnSwitchToLogin} />, { wrapper });

    const loginLink = screen.getByText("Already have an account? Login");
    await userEvent.click(loginLink);

    expect(mockOnSwitchToLogin).toHaveBeenCalledTimes(1);
  });

  it("requires email and password fields", () => {
    render(<Register onSwitchToLogin={mockOnSwitchToLogin} />, { wrapper });

    const emailInput = screen.getByLabelText("Email *");
    const passwordInput = screen.getByLabelText("Password (min. 6 characters) *");
    const confirmPasswordInput = screen.getByLabelText("Confirm Password *");

    expect(emailInput).toBeRequired();
    expect(passwordInput).toBeRequired();
    expect(confirmPasswordInput).toBeRequired();
  });

  it("handles optional name and surname fields", async () => {
    const mockRegisterResponse = { success: true };
    const mockTokenResponse = { access_token: "test-token" };
    const mockUserResponse = {
      id: 1,
      email: "minimal@example.com",
      name: null,
      surname: null,
      timezone: null,
      pages_recognised_count: 0,
    };

    (global.fetch as any)
      .mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockRegisterResponse),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockTokenResponse),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockUserResponse),
      });

    render(<Register onSwitchToLogin={mockOnSwitchToLogin} />, { wrapper });

    const emailInput = screen.getByLabelText("Email *");
    const passwordInput = screen.getByLabelText("Password (min. 6 characters) *");
    const confirmPasswordInput = screen.getByLabelText("Confirm Password *");
    const registerButton = screen.getByRole("button", { name: "Register" });

    await userEvent.type(emailInput, "minimal@example.com");
    await userEvent.type(passwordInput, "password123");
    await userEvent.type(confirmPasswordInput, "password123");
    await userEvent.click(registerButton);

    await waitFor(() => {
      expect(global.fetch).toHaveBeenCalledWith(
        "http://localhost:8000/auth/register",
        expect.objectContaining({
          method: "POST",
          body: JSON.stringify({
            email: "minimal@example.com",
            password: "password123",
            name: undefined,
            surname: undefined,
          }),
        })
      );
    });
  });
});
