import { describe, expect, it } from "vitest";
import { appendTranscribedTextToInput } from "./chatInputText";

describe("appendTranscribedTextToInput", () => {
  it("returns the transcription when input is empty", () => {
    expect(appendTranscribedTextToInput("", "hur mar du?")).toBe("hur mar du?");
  });

  it("adds a separating space when neither side provides one", () => {
    expect(appendTranscribedTextToInput("Hej", "hur mar du?")).toBe("Hej hur mar du?");
  });

  it("does not add an extra space when input already ends with whitespace", () => {
    expect(appendTranscribedTextToInput("Hej ", "hur mar du?")).toBe("Hej hur mar du?");
  });

  it("does not add an extra space when transcription starts with whitespace", () => {
    expect(appendTranscribedTextToInput("Hej", " hur mar du?")).toBe("Hej hur mar du?");
  });
});
