/// <reference types="vitest/globals" />
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import VocabularyOverview from "./VocabularyOverview";
import { getActiveSegmentCount } from "./visualization";

describe("getActiveSegmentCount", () => {
  it("keeps a zero metric visually empty", () => {
    expect(getActiveSegmentCount(0, 100)).toBe(0);
  });

  it("keeps a positive metric visible", () => {
    expect(getActiveSegmentCount(1, 1_000)).toBe(1);
  });
});

describe("VocabularyOverview", () => {
  it("does not render a redundant progress strip for Overall Words", () => {
    render(
      <VocabularyOverview
        loading={false}
        stats={{
          words_in_learn_count: 12,
          words_skipped_count: 4,
          overall_words_count: 20,
          words_prioritized_count: 3,
        }}
      />
    );

    expect(screen.queryByTestId("overall_words_count-segments")).not.toBeInTheDocument();
    expect(screen.getByTestId("words_skipped_count-segments")).toBeInTheDocument();
    expect(screen.getByTestId("words_prioritized_count-segments")).toBeInTheDocument();
  });
});
