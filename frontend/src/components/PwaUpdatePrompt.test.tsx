import React from "react";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi, beforeEach } from "vitest";

const updateServiceWorkerMock = vi.fn();
const registerErrorCallbackMock = vi.fn();

const mockState: {
  needRefresh: [boolean, (v: boolean) => void];
  onRegisterError?: (error: Error) => void;
} = {
  needRefresh: [false, () => {}],
};

vi.mock("virtual:pwa-register/react", () => ({
  useRegisterSW: (options?: {
    onRegisterError?: (error: Error) => void;
  }) => {
    mockState.onRegisterError = options?.onRegisterError;
    return {
      needRefresh: mockState.needRefresh,
      updateServiceWorker: updateServiceWorkerMock,
    };
  },
}));

import PwaUpdatePrompt from "./PwaUpdatePrompt";

const setNeedRefresh = (value: boolean) => {
  mockState.needRefresh = [value, () => {}];
};

describe("PwaUpdatePrompt", () => {
  beforeEach(() => {
    updateServiceWorkerMock.mockClear();
    registerErrorCallbackMock.mockClear();
    setNeedRefresh(false);
  });

  it("does not render when no update is pending", () => {
    render(<PwaUpdatePrompt />);
    expect(screen.queryByRole("alertdialog")).not.toBeInTheDocument();
  });

  it("renders the prompt when needRefresh is raised", () => {
    setNeedRefresh(true);
    render(<PwaUpdatePrompt />);
    expect(screen.getByRole("alertdialog")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /reload/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /later/i })).toBeInTheDocument();
  });

  it("calls updateServiceWorker(true) only after the user chooses Reload", async () => {
    const user = userEvent.setup();
    setNeedRefresh(true);
    render(<PwaUpdatePrompt />);

    expect(updateServiceWorkerMock).not.toHaveBeenCalled();
    await user.click(screen.getByRole("button", { name: /reload/i }));

    await waitFor(() => {
      expect(updateServiceWorkerMock).toHaveBeenCalledWith(true);
    });
  });

  it("hides the prompt and keeps the page when the user chooses Later", async () => {
    const user = userEvent.setup();
    setNeedRefresh(true);
    render(<PwaUpdatePrompt />);

    await user.click(screen.getByRole("button", { name: /later/i }));

    await waitFor(() => {
      expect(screen.queryByRole("alertdialog")).not.toBeInTheDocument();
    });
    expect(updateServiceWorkerMock).not.toHaveBeenCalled();
  });

  it("reports registration errors through the plugin callback", () => {
    const consoleErrorSpy = vi
      .spyOn(console, "error")
      .mockImplementation(() => {});
    render(<PwaUpdatePrompt />);

    expect(mockState.onRegisterError).toBeDefined();
    mockState.onRegisterError!(new Error("registration failed"));

    expect(consoleErrorSpy).toHaveBeenCalledWith(
      "Service worker registration failed:",
      expect.any(Error),
    );
    consoleErrorSpy.mockRestore();
  });
});
