import { act, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { TeacherAvatar } from "./TeacherAvatar";

describe("TeacherAvatar", () => {
  afterEach(() => {
    vi.useRealTimers();
  });

  it("keeps the previous emotion image during crossfade and clears it after the transition", () => {
    vi.useFakeTimers();

    const { container, rerender } = render(<TeacherAvatar emotion="neutral" />);

    expect(
      screen.getByRole("img", { name: /björn, your swedish teacher/i }),
    ).toHaveAttribute("src", expect.stringContaining("bjorn_neutral"));
    expect(container.querySelectorAll("img")).toHaveLength(1);

    rerender(<TeacherAvatar emotion="happy" />);

    expect(
      screen.getByRole("img", { name: /björn, your swedish teacher/i }),
    ).toHaveAttribute("src", expect.stringContaining("bjorn_happy"));
    expect(container.querySelectorAll("img")).toHaveLength(2);
    expect(container.querySelector("img[aria-hidden='true']")).toHaveAttribute(
      "src",
      expect.stringContaining("bjorn_neutral"),
    );

    act(() => {
      vi.advanceTimersByTime(1799);
    });
    expect(container.querySelectorAll("img")).toHaveLength(2);

    act(() => {
      vi.advanceTimersByTime(1);
    });
    expect(container.querySelectorAll("img")).toHaveLength(1);
    expect(
      screen.getByRole("img", { name: /björn, your swedish teacher/i }),
    ).toHaveAttribute("src", expect.stringContaining("bjorn_happy"));
  });

  it("resets the cleanup timer when the emotion changes again mid-crossfade", () => {
    vi.useFakeTimers();

    const { container, rerender } = render(<TeacherAvatar emotion="neutral" />);

    rerender(<TeacherAvatar emotion="happy" />);
    act(() => {
      vi.advanceTimersByTime(900);
    });

    rerender(<TeacherAvatar emotion="sad" />);

    expect(
      screen.getByRole("img", { name: /björn, your swedish teacher/i }),
    ).toHaveAttribute("src", expect.stringContaining("bjorn_sad"));
    expect(container.querySelectorAll("img")).toHaveLength(2);
    expect(container.querySelector("img[aria-hidden='true']")).toHaveAttribute(
      "src",
      expect.stringContaining("bjorn_happy"),
    );

    act(() => {
      vi.advanceTimersByTime(900);
    });
    expect(container.querySelectorAll("img")).toHaveLength(2);

    act(() => {
      vi.advanceTimersByTime(900);
    });
    expect(container.querySelectorAll("img")).toHaveLength(1);
    expect(
      screen.getByRole("img", { name: /björn, your swedish teacher/i }),
    ).toHaveAttribute("src", expect.stringContaining("bjorn_sad"));
  });
});
