import { act, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { TeacherAvatar } from "./TeacherAvatar";

describe("TeacherAvatar", () => {
  const CROSSFADE_MS = 1800;
  const HALF_CROSSFADE_MS = CROSSFADE_MS / 2;

  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("keeps the previous emotion image during crossfade and clears it after the transition", () => {
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
      vi.advanceTimersByTime(CROSSFADE_MS - 1);
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
    const { container, rerender } = render(<TeacherAvatar emotion="neutral" />);

    rerender(<TeacherAvatar emotion="happy" />);
    act(() => {
      vi.advanceTimersByTime(HALF_CROSSFADE_MS);
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
      vi.advanceTimersByTime(HALF_CROSSFADE_MS);
    });
    expect(container.querySelectorAll("img")).toHaveLength(2);

    act(() => {
      vi.advanceTimersByTime(HALF_CROSSFADE_MS);
    });
    expect(container.querySelectorAll("img")).toHaveLength(1);
    expect(
      screen.getByRole("img", { name: /björn, your swedish teacher/i }),
    ).toHaveAttribute("src", expect.stringContaining("bjorn_sad"));
  });
});
