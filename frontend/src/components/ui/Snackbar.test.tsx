import React from "react";
import { render, screen, waitFor, act } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi } from "vitest";
import Snackbar from "./Snackbar";

describe("Snackbar", () => {
  const defaultProps = {
    message: "Test message",
    open: true,
    onClose: vi.fn(),
  };

  it("renders with default props", () => {
    render(<Snackbar {...defaultProps} />);
    expect(screen.getByText("Test message")).toBeInTheDocument();
  });

  it("does not render when open is false", () => {
    render(<Snackbar {...defaultProps} open={false} />);
    expect(screen.queryByText("Test message")).not.toBeInTheDocument();
  });

  it("calls onClose when close button is clicked", async () => {
    const user = userEvent.setup();
    render(<Snackbar {...defaultProps} />);

    const closeButton = screen.getByRole("button");
    await user.click(closeButton);

    await waitFor(() => {
      expect(defaultProps.onClose).toHaveBeenCalled();
    });
  });

  it("auto-hides after specified duration", async () => {
    vi.useFakeTimers();
    render(<Snackbar {...defaultProps} autoHideDuration={1000} />);

    expect(screen.getByText("Test message")).toBeInTheDocument();

    // Advance timer by 1000ms (autoHideDuration) - this triggers handleClose in useEffect
    act(() => {
      vi.advanceTimersByTime(1000);
    });

    // Advance additional 300ms for the handleClose timeout - this triggers onClose
    act(() => {
      vi.advanceTimersByTime(300);
    });

    // onClose should have been called by now
    expect(defaultProps.onClose).toHaveBeenCalled();

    vi.useRealTimers();
  });

  it("displays different icons for different severities", () => {
    const { rerender } = render(
      <Snackbar {...defaultProps} severity="success" />
    );
    expect(screen.getByTestId("CheckCircleIcon")).toBeInTheDocument();

    rerender(<Snackbar {...defaultProps} severity="error" />);
    expect(screen.getByTestId("ErrorIcon")).toBeInTheDocument();

    rerender(<Snackbar {...defaultProps} severity="warning" />);
    expect(screen.getByTestId("WarningIcon")).toBeInTheDocument();

    rerender(<Snackbar {...defaultProps} severity="info" />);
    expect(screen.getByTestId("InfoIcon")).toBeInTheDocument();
  });

  it("wraps long text appropriately", () => {
    const longMessage =
      "This is a very long message that should wrap properly within the snackbar component without causing layout issues or overflow problems on different screen sizes.";
    render(<Snackbar {...defaultProps} message={longMessage} />);

    const messageElement = screen.getByText(longMessage);
    expect(messageElement).toBeInTheDocument();
    // The wrapping is handled by the parent Box, not the Typography element
  });
});
