/// <reference types="vitest/globals" />
import { describe, expect, it } from "vitest";
import { getActiveSegmentCount } from "./visualization";

describe("getActiveSegmentCount", () => {
  it("keeps a zero metric visually empty", () => {
    expect(getActiveSegmentCount(0, 100)).toBe(0);
  });

  it("keeps a positive metric visible", () => {
    expect(getActiveSegmentCount(1, 1_000)).toBe(1);
  });
});
