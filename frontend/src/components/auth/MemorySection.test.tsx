
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { MemorySection } from "./MemorySection";
import * as useAuthHook from "../../hooks/useAuth";
import type { UserData } from "../../types/auth";
import { vi, describe, it, expect, beforeEach } from "vitest";

// Partially mock useAuth
vi.mock("../../hooks/useAuth", () => ({
  useAuthActions: vi.fn(),
}));

const mockUserData: UserData = {
  id: 1,
  email: "test@example.com",
  name: "Test User",
  surname: "Tester",
  timezone: "UTC",
  pages_recognised_count: 0,
  words_skipped_count: 0,
  overall_words_count: 0,
  personal_info: { name: "Test" },
  areas_to_improve: null,
  knowledge_strengths: {},
};

const mockUpdateProfile = vi.fn();
const mockClearMemory = vi.fn();

describe("MemorySection", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(useAuthHook.useAuthActions).mockReturnValue({
      login: vi.fn(),
      register: vi.fn(),
      logout: vi.fn(),
      error: null,
      updateProfile: mockUpdateProfile,
      clearMemory: mockClearMemory,
      loading: false,
    });
  });

  it("renders correctly with mixed data", () => {
    render(<MemorySection userData={mockUserData} />);

    // Check main title
    expect(screen.getByText("Björn's Memory")).toBeInTheDocument();

    // Check sections
    expect(screen.getByText("Personal Info")).toBeInTheDocument();
    expect(screen.getByText("Areas to Improve")).toBeInTheDocument();
    expect(screen.getByText("Knowledge Strengths")).toBeInTheDocument();

    // Check content
    expect(screen.getByText(/"name": "Test"/)).toBeInTheDocument();
    expect(screen.getAllByText("No memory stored for this category yet.")).toHaveLength(2);
  });

  it("handles edit and save flow", async () => {
    render(<MemorySection userData={mockUserData} />);

    // Open accordion
    fireEvent.click(screen.getByText("Björn's Memory"));

    // Find edit button for Personal Info (first one)
    const editButtons = screen.getAllByTestId("EditIcon");
    fireEvent.click(editButtons[0].closest("button")!);

    // Edit content
    const input = screen.getByRole("textbox");
    fireEvent.change(input, { target: { value: '{"name": "Updated"}' } });

    // Save
    const saveButton = screen.getByTestId("SaveIcon").closest("button")!;
    fireEvent.click(saveButton);

    await waitFor(() => {
      expect(mockUpdateProfile).toHaveBeenCalledWith({
        personal_info: { name: "Updated" },
      });
    });
  });

  it("shows error for invalid JSON", async () => {
    render(<MemorySection userData={mockUserData} />);

    // Open accordion
    fireEvent.click(screen.getByText("Björn's Memory"));

    const editButtons = screen.getAllByTestId("EditIcon");
    fireEvent.click(editButtons[0].closest("button")!);

    const input = screen.getByRole("textbox");
    fireEvent.change(input, { target: { value: '{invalid json' } });

    const saveButton = screen.getByTestId("SaveIcon").closest("button")!;
    fireEvent.click(saveButton);

    expect(await screen.findByText("Invalid JSON format")).toBeInTheDocument();
    expect(mockUpdateProfile).not.toHaveBeenCalled();
  });

  it("handles clear individual category", async () => {
    render(<MemorySection userData={mockUserData} />);

    // Open accordion
    fireEvent.click(screen.getByText("Björn's Memory"));

    // Find clear button for Personal Info
    const clearButtons = screen.getAllByTestId("DeleteIcon");
    // First clear button is for Personal Info (index 0)
    // Note: The big "Clear All" button also has a DeleteIcon, but it's at the end
    fireEvent.click(clearButtons[0].closest("button")!);

    // Confirm dialog
    expect(screen.getByText(/Are you sure you want to clear the personal info memory/)).toBeInTheDocument();
    fireEvent.click(screen.getByText("Clear"));

    await waitFor(() => {
      expect(mockClearMemory).toHaveBeenCalledWith("personal_info");
    });
  });

  it("handles clear all memory", async () => {
    render(<MemorySection userData={mockUserData} />);

    // Open accordion
    fireEvent.click(screen.getByText("Björn's Memory"));

    const clearAllButton = screen.getByText("Clear All Memory");
    fireEvent.click(clearAllButton);

    expect(screen.getByText(/Are you sure you want to clear ALL memory/)).toBeInTheDocument();
    fireEvent.click(screen.getByText("Clear"));

    await waitFor(() => {
      expect(mockClearMemory).toHaveBeenCalledWith(); // called with undefined
    });
  });
});
