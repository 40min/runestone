import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi } from "vitest";
import Profile from "./Profile";
import { AuthProvider } from "../../context/AuthContext";

// Mock config
vi.mock("../../config", () => ({
  API_BASE_URL: "http://localhost:8010",
}));

// Mock fetch
global.fetch = vi.fn();

describe("Profile", () => {
  const mockUserData = {
    id: 1,
    email: "test@example.com",
    name: "Test",
    surname: "User",
    timezone: "UTC",
    pages_recognised_count: 10,
    words_in_learn_count: 25,
    words_learned_count: 150,
  };

  const wrapper = ({ children }: { children: React.ReactNode }) => {
    // Mock authenticated state
    const mockLocalStorage = {
      getItem: vi.fn((key: string) => {
        if (key === "runestone_token") return "test-token";
        if (key === "runestone_user_data") return JSON.stringify(mockUserData);
        return null;
      }),
      setItem: vi.fn(),
      removeItem: vi.fn(),
    };
    Object.defineProperty(window, "localStorage", { value: mockLocalStorage });

    return <AuthProvider>{children}</AuthProvider>;
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders profile data correctly", () => {
    render(<Profile />, { wrapper });

    expect(screen.getByText("Profile")).toBeInTheDocument();
    expect(screen.getByText("Email: test@example.com")).toBeInTheDocument();
    expect(screen.getAllByText("Pages Recognised:")[0]).toBeInTheDocument();
    expect(screen.getByText("10")).toBeInTheDocument();
    expect(screen.getAllByText("Words Learning:")[0]).toBeInTheDocument();
    expect(screen.getByText("25")).toBeInTheDocument();
    expect(screen.getAllByText("Words Learned:")[0]).toBeInTheDocument();
    expect(screen.getByText("150")).toBeInTheDocument();
  });

  it("displays form fields with user data", () => {
    render(<Profile />, { wrapper });

    expect(screen.getByDisplayValue("Test")).toBeInTheDocument(); // name
    expect(screen.getByDisplayValue("User")).toBeInTheDocument(); // surname
    expect(screen.getByDisplayValue("UTC")).toBeInTheDocument(); // timezone
  });

  it("handles successful profile update", async () => {
    const updatedUserData = {
      ...mockUserData,
      name: "Updated",
      surname: "Name",
      timezone: "EST",
    };

    vi.mocked(global.fetch).mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve(updatedUserData),
    } as Response);

    render(<Profile />, { wrapper });

    const nameInput = screen.getByLabelText("Name");
    const surnameInput = screen.getByLabelText("Surname");
    const timezoneInput = screen.getByLabelText("Timezone");
    const updateButton = screen.getByRole("button", { name: "Update Profile" });

    await userEvent.clear(nameInput);
    await userEvent.type(nameInput, "Updated");
    await userEvent.clear(surnameInput);
    await userEvent.type(surnameInput, "Name");
    await userEvent.clear(timezoneInput);
    await userEvent.type(timezoneInput, "EST");
    await userEvent.click(updateButton);

    await waitFor(() => {
      expect(global.fetch).toHaveBeenCalledWith(
        "http://localhost:8010/users/me",
        expect.objectContaining({
          method: "PUT",
          body: JSON.stringify({
            name: "Updated",
            surname: "Name",
            timezone: "EST",
          }),
        })
      );
    });

    expect(
      screen.getByText("Profile updated successfully!")
    ).toBeInTheDocument();
  });

  it("handles profile update failure", async () => {
    vi.mocked(global.fetch).mockResolvedValueOnce({
      ok: false,
      json: () => Promise.resolve({ detail: "Update failed" }),
    } as Response);

    render(<Profile />, { wrapper });

    const nameInput = screen.getByLabelText("Name");
    const updateButton = screen.getByRole("button", { name: "Update Profile" });

    await userEvent.clear(nameInput);
    await userEvent.type(nameInput, "New Name");
    await userEvent.click(updateButton);

    await waitFor(() => {
      expect(screen.getByText("Update failed")).toBeInTheDocument();
    });
  });

  it("validates password change", async () => {
    render(<Profile />, { wrapper });

    const passwordInput = screen.getByLabelText("New Password (optional)");
    const confirmPasswordInput = screen.getByLabelText("Confirm New Password");
    const updateButton = screen.getByRole("button", { name: "Update Profile" });

    await userEvent.type(passwordInput, "newpassword");
    await userEvent.type(confirmPasswordInput, "differentpassword");
    await userEvent.click(updateButton);

    expect(screen.getByText("Passwords do not match")).toBeInTheDocument();
    expect(global.fetch).not.toHaveBeenCalled();
  });

  it("validates password length", async () => {
    render(<Profile />, { wrapper });

    const passwordInput = screen.getByLabelText("New Password (optional)");
    const confirmPasswordInput = screen.getByLabelText("Confirm New Password");
    const updateButton = screen.getByRole("button", { name: "Update Profile" });

    await userEvent.type(passwordInput, "12345"); // Less than 6 characters
    await userEvent.type(confirmPasswordInput, "12345");
    await userEvent.click(updateButton);

    expect(
      screen.getByText("Password must be at least 6 characters")
    ).toBeInTheDocument();
    expect(global.fetch).not.toHaveBeenCalled();
  });

  it("shows loading state during update", async () => {
    vi.mocked(global.fetch).mockImplementation(
      () =>
        new Promise((resolve) =>
          setTimeout(
            () =>
              resolve({
                ok: true,
                json: () => Promise.resolve(mockUserData),
              } as Response),
            100
          )
        )
    );

    render(<Profile />, { wrapper });

    const updateButton = screen.getByRole("button", { name: "Update Profile" });
    await userEvent.click(updateButton);

    expect(screen.getByText("Updating...")).toBeInTheDocument();

    await waitFor(() => {
      expect(screen.queryByText("Updating...")).not.toBeInTheDocument();
    });
  });

  it("clears password fields after successful update", async () => {
    const updatedUserData = {
      ...mockUserData,
      name: "New Name",
    };

    vi.mocked(global.fetch).mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve(updatedUserData),
    } as Response);

    render(<Profile />, { wrapper });

    const passwordInput = screen.getByLabelText("New Password (optional)");
    const confirmPasswordInput = screen.getByLabelText("Confirm New Password");
    const updateButton = screen.getByRole("button", { name: "Update Profile" });

    await userEvent.type(passwordInput, "newpassword123");
    await userEvent.type(confirmPasswordInput, "newpassword123");
    await userEvent.click(updateButton);

    await waitFor(() => {
      expect(passwordInput).toHaveValue("");
      expect(confirmPasswordInput).toHaveValue("");
    });
  });

  it("renders all three stats correctly", () => {
    render(<Profile />, { wrapper });

    expect(screen.getAllByText("Pages Recognised:")[0]).toBeInTheDocument();
    expect(screen.getByText("10")).toBeInTheDocument();
    expect(screen.getAllByText("Words Learning:")[0]).toBeInTheDocument();
    expect(screen.getByText("25")).toBeInTheDocument();
    expect(screen.getAllByText("Words Learned:")[0]).toBeInTheDocument();
    expect(screen.getByText("150")).toBeInTheDocument();
  });

  it("handles null values in stats by displaying zero", () => {
    const userDataWithNulls = {
      ...mockUserData,
      words_in_learn_count: null,
      words_learned_count: null,
    };

    const wrapperWithNulls = ({ children }: { children: React.ReactNode }) => {
      const mockLocalStorage = {
        getItem: vi.fn((key: string) => {
          if (key === "runestone_token") return "test-token";
          if (key === "runestone_user_data")
            return JSON.stringify(userDataWithNulls);
          return null;
        }),
        setItem: vi.fn(),
        removeItem: vi.fn(),
      };
      Object.defineProperty(window, "localStorage", {
        value: mockLocalStorage,
      });

      return <AuthProvider>{children}</AuthProvider>;
    };

    render(<Profile />, { wrapper: wrapperWithNulls });

    // Verify labels exist
    expect(screen.getByText("Words Learning:")).toBeInTheDocument();
    expect(screen.getByText("Words Learned:")).toBeInTheDocument();

    // Verify null values are displayed as 0
    const statsSection = screen.getByText("Words Learning:").closest("div");
    expect(statsSection).toHaveTextContent("0");

    const learnedSection = screen.getByText("Words Learned:").closest("div");
    expect(learnedSection).toHaveTextContent("0");
  });

  it("handles timezone selection", async () => {
    const updatedUserData = {
      ...mockUserData,
      timezone: "America/New_York",
    };

    vi.mocked(global.fetch).mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve(updatedUserData),
    } as Response);

    render(<Profile />, { wrapper });

    const timezoneInput = screen.getByLabelText("Timezone");
    const updateButton = screen.getByRole("button", { name: "Update Profile" });

    await userEvent.clear(timezoneInput);
    await userEvent.type(timezoneInput, "America/New_York");
    await userEvent.click(updateButton);

    await waitFor(() => {
      expect(global.fetch).toHaveBeenCalledWith(
        "http://localhost:8010/users/me",
        expect.objectContaining({
          body: JSON.stringify({
            name: "Test",
            surname: "User",
            timezone: "America/New_York",
          }),
        })
      );
    });
  });

  it("handles successful password change", async () => {
    const updatedUserData = { ...mockUserData };

    vi.mocked(global.fetch).mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve(updatedUserData),
    } as Response);

    render(<Profile />, { wrapper });

    const passwordInput = screen.getByLabelText("New Password (optional)");
    const confirmPasswordInput = screen.getByLabelText("Confirm New Password");
    const updateButton = screen.getByRole("button", { name: "Update Profile" });

    await userEvent.type(passwordInput, "newpassword123");
    await userEvent.type(confirmPasswordInput, "newpassword123");
    await userEvent.click(updateButton);

    await waitFor(() => {
      expect(global.fetch).toHaveBeenCalledWith(
        "http://localhost:8010/users/me",
        expect.objectContaining({
          body: JSON.stringify({
            name: "Test",
            surname: "User",
            timezone: "UTC",
            password: "newpassword123",
          }),
        })
      );
    });

    expect(
      screen.getByText("Profile updated successfully!")
    ).toBeInTheDocument();
  });

  it("handles partial profile update (only name)", async () => {
    const updatedUserData = {
      ...mockUserData,
      name: "NewName",
    };

    vi.mocked(global.fetch).mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve(updatedUserData),
    } as Response);

    render(<Profile />, { wrapper });

    const nameInput = screen.getByLabelText("Name");
    const updateButton = screen.getByRole("button", { name: "Update Profile" });

    await userEvent.clear(nameInput);
    await userEvent.type(nameInput, "NewName");
    await userEvent.click(updateButton);

    await waitFor(() => {
      expect(global.fetch).toHaveBeenCalledWith(
        "http://localhost:8010/users/me",
        expect.objectContaining({
          body: JSON.stringify({
            name: "NewName",
            surname: "User",
            timezone: "UTC",
          }),
        })
      );
    });
  });

  it("handles partial profile update (only timezone)", async () => {
    const updatedUserData = {
      ...mockUserData,
      timezone: "PST",
    };

    vi.mocked(global.fetch).mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve(updatedUserData),
    } as Response);

    render(<Profile />, { wrapper });

    const timezoneInput = screen.getByLabelText("Timezone");
    const updateButton = screen.getByRole("button", { name: "Update Profile" });

    await userEvent.clear(timezoneInput);
    await userEvent.type(timezoneInput, "PST");
    await userEvent.click(updateButton);

    await waitFor(() => {
      expect(global.fetch).toHaveBeenCalledWith(
        "http://localhost:8010/users/me",
        expect.objectContaining({
          body: JSON.stringify({
            name: "Test",
            surname: "User",
            timezone: "PST",
          }),
        })
      );
    });
  });

  it("does not render when userData is null", () => {
    const wrapperWithNoUser = ({ children }: { children: React.ReactNode }) => {
      const mockLocalStorage = {
        getItem: vi.fn(() => null),
        setItem: vi.fn(),
        removeItem: vi.fn(),
      };
      Object.defineProperty(window, "localStorage", {
        value: mockLocalStorage,
      });

      return <AuthProvider>{children}</AuthProvider>;
    };

    const { container } = render(<Profile />, { wrapper: wrapperWithNoUser });
    expect(container.firstChild).toBeNull();
  });

  it("handles password update with profile changes", async () => {
    const updatedUserData = {
      ...mockUserData,
      name: "Password",
      surname: "Changed",
    };

    vi.mocked(global.fetch).mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve(updatedUserData),
    } as Response);

    render(<Profile />, { wrapper });

    const nameInput = screen.getByLabelText("Name");
    const surnameInput = screen.getByLabelText("Surname");
    const passwordInput = screen.getByLabelText("New Password (optional)");
    const confirmPasswordInput = screen.getByLabelText("Confirm New Password");
    const updateButton = screen.getByRole("button", { name: "Update Profile" });

    await userEvent.clear(nameInput);
    await userEvent.type(nameInput, "Password");
    await userEvent.clear(surnameInput);
    await userEvent.type(surnameInput, "Changed");
    await userEvent.type(passwordInput, "newpassword123");
    await userEvent.type(confirmPasswordInput, "newpassword123");
    await userEvent.click(updateButton);

    await waitFor(() => {
      expect(global.fetch).toHaveBeenCalledWith(
        "http://localhost:8010/users/me",
        expect.objectContaining({
          method: "PUT",
          body: JSON.stringify({
            name: "Password",
            surname: "Changed",
            timezone: "UTC",
            password: "newpassword123",
          }),
        })
      );
    });
  });
});
