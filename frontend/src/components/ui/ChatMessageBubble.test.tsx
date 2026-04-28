import { render, screen } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import React from "react";
import userEvent from "@testing-library/user-event";
import { ChatMessageBubble } from "./ChatMessageBubble";
import { formatResponseTime } from "./ChatMessageBubble.utils";

describe("ChatMessageBubble", () => {
  it("renders assistant sources with link and date", () => {
    render(
      <ChatMessageBubble
        role="assistant"
        content="Här är nyheterna"
        sources={[
          {
            title: "Nyhetstitel",
            url: "https://example.com/news",
            date: "2026-02-05",
          },
        ]}
      />,
    );

    expect(screen.getByText("Sources")).toBeInTheDocument();
    const link = screen.getByRole("link", { name: "Nyhetstitel" });
    expect(link).toHaveAttribute("href", "https://example.com/news");
    expect(link).toHaveAttribute("target", "_blank");
    expect(link).toHaveAttribute("rel", "noopener noreferrer");
    expect(screen.getByText("2026-02-05")).toBeInTheDocument();
  });

  it("renders the teacher avatar for assistant messages", () => {
    render(<ChatMessageBubble role="assistant" content="Hej!" />);

    expect(
      screen.getByRole("img", { name: /björn, your swedish teacher/i }),
    ).toBeInTheDocument();
  });

  it("renders the requested teacher emotion avatar", () => {
    render(
      <ChatMessageBubble
        role="assistant"
        content="Bra jobbat!"
        teacherEmotion="happy"
      />,
    );

    expect(
      screen.getByRole("img", { name: /björn, your swedish teacher/i }),
    ).toHaveAttribute("src", expect.stringContaining("bjorn_happy"));
  });

  it("renders a student avatar and no teacher avatar for user messages", () => {
    render(<ChatMessageBubble role="user" content="Hej!" />);

    expect(
      screen.queryByRole("img", { name: /björn, your swedish teacher/i }),
    ).not.toBeInTheDocument();
    expect(screen.getByRole("img", { name: /you, student/i })).toBeInTheDocument();
  });

  it("renders provided student avatar initials for user messages", () => {
    render(
      <ChatMessageBubble
        role="user"
        content="Hej!"
        studentAvatarLabel="AS"
      />,
    );

    expect(screen.getByRole("img", { name: /as, student/i })).toBeInTheDocument();
    expect(screen.getByText("AS")).toBeInTheDocument();
  });

  it("renders assistant markdown formatting", () => {
    render(
      <ChatMessageBubble
        role="assistant"
        content='Det var **"en vanlig dag"**, alltså!'
      />,
    );

    expect(screen.getByText('"en vanlig dag"').tagName).toBe("STRONG");
    expect(screen.queryByText(/\*\*/)).not.toBeInTheDocument();
  });

  it("renders teaching callouts for correction snippets", () => {
    render(
      <ChatMessageBubble
        role="assistant"
        content={'Bra jobbat.\n\n💡 **"Den sjätte januari"**.'}
      />,
    );

    expect(screen.getByTestId("teaching-callout")).toBeInTheDocument();
    expect(screen.getByText('"Den sjätte januari"').tagName).toBe("STRONG");
  });

  it("renders a subtle message timestamp when createdAt is provided", () => {
    render(
      <ChatMessageBubble
        role="assistant"
        content="Hej!"
        createdAt="2026-04-15T10:22:00Z"
      />,
    );

    expect(screen.getByText(/\d{1,2}:\d{2}/)).toBeInTheDocument();
  });

  it("does not render sources for user messages", () => {
    render(
      <ChatMessageBubble
        role="user"
        content="Hej!"
        sources={[
          {
            title: "Nyhetstitel",
            url: "https://example.com/news",
            date: "2026-02-05",
          },
        ]}
      />,
    );

    expect(screen.queryByText("Sources")).not.toBeInTheDocument();
    expect(
      screen.queryByRole("link", { name: "Nyhetstitel" }),
    ).not.toBeInTheDocument();
  });

  it("renders invalid source URLs as plain text", () => {
    render(
      <ChatMessageBubble
        role="assistant"
        content="Här är nyheterna"
        sources={[
          {
            title: "Skum länk",
            url: "javascript:alert(1)",
            date: "2026-02-05",
          },
        ]}
      />,
    );

    expect(screen.getByText("Sources")).toBeInTheDocument();
    expect(screen.getByText("Skum länk")).toBeInTheDocument();
    expect(
      screen.queryByRole("link", { name: "Skum länk" }),
    ).not.toBeInTheDocument();
  });

  it("collapses long messages and toggles via button", async () => {
    const user = userEvent.setup();
    const longText = "a".repeat(301);
    render(<ChatMessageBubble role="user" content={longText} />);

    expect(screen.getByText("a".repeat(300))).toBeInTheDocument();
    expect(screen.getByText("...")).toBeInTheDocument();
    expect(screen.queryByText(longText)).not.toBeInTheDocument();

    const showMoreBtn = screen.getByRole("button", { name: /show more/i });
    await user.click(showMoreBtn);

    expect(screen.getByText(longText)).toBeInTheDocument();
    expect(screen.queryByText("...")).not.toBeInTheDocument();

    const showLessBtn = screen.getByRole("button", { name: /show less/i });
    await user.click(showLessBtn);

    expect(screen.getByText("a".repeat(300))).toBeInTheDocument();
    expect(screen.getByText("...")).toBeInTheDocument();
  });

  it("does not collapse long messages if isLast is true", () => {
    const longText = "a".repeat(301);
    render(
      <ChatMessageBubble role="user" content={longText} isLast={true} />,
    );

    expect(screen.getByText(longText)).toBeInTheDocument();
    expect(screen.queryByText("...")).not.toBeInTheDocument();
  });

  it("collapses long assistant teaching messages", () => {
    const longText = "a".repeat(320);
    render(<ChatMessageBubble role="assistant" content={longText} />);

    expect(screen.getByText("a".repeat(300))).toBeInTheDocument();
    expect(screen.getByText("...")).toBeInTheDocument();
  });

  it("does not collapse long messages when latest by role", () => {
    const longText = "a".repeat(301);
    render(
      <ChatMessageBubble role="assistant" content={longText} isLatestByRole={true} />,
    );

    expect(screen.getByText("a".repeat(301))).toBeInTheDocument();
    expect(screen.queryByText("...")).not.toBeInTheDocument();
  });

  it("renders assistant response time as visible copy", () => {
    render(
      <ChatMessageBubble
        role="assistant"
        content="Snabbt svar"
        responseTimeMs={1420}
      />,
    );

    expect(screen.getByText("Teacher responded in 1.4 s")).toBeInTheDocument();
  });

  it("does not render response time for user messages", () => {
    render(
      <ChatMessageBubble role="user" content="Hej!" responseTimeMs={250} />,
    );

    expect(screen.queryByText(/Teacher responded in/i)).not.toBeInTheDocument();
  });

  it("formats response time for milliseconds and seconds", () => {
    expect(formatResponseTime(420)).toBe("420 ms");
    expect(formatResponseTime(1420)).toBe("1.4 s");
    expect(formatResponseTime(10999)).toBe("11 s");
  });

  it("renders audio controls only when explicitly enabled", () => {
    const onPlay = vi.fn();
    const onReplay = vi.fn();

    render(
      <ChatMessageBubble
        role="assistant"
        content="Lyssna här"
        showAudioControls={true}
        canReplayAudio={true}
        onPlayAudio={onPlay}
        onReplayAudio={onReplay}
      />,
    );

    expect(screen.getByRole("button", { name: /^play$/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /^replay$/i })).toBeInTheDocument();
  });

  it("swaps play for pause when audio is playing", async () => {
    const user = userEvent.setup();
    const onPause = vi.fn();
    const onReplay = vi.fn();

    render(
      <ChatMessageBubble
        role="assistant"
        content="Lyssna här"
        showAudioControls={true}
        isAudioPlaying={true}
        canReplayAudio={true}
        onPauseAudio={onPause}
        onReplayAudio={onReplay}
      />,
    );

    expect(screen.queryByRole("button", { name: /^play$/i })).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /^pause$/i }));
    expect(onPause).toHaveBeenCalledOnce();

    await user.click(screen.getByRole("button", { name: /^replay$/i }));
    expect(onReplay).toHaveBeenCalledOnce();
  });

  it("does not render audio controls for user messages", () => {
    render(
      <ChatMessageBubble
        role="user"
        content="Hej!"
        showAudioControls={true}
        canReplayAudio={true}
      />,
    );

    expect(screen.queryByRole("button", { name: /^play$/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /^replay$/i })).not.toBeInTheDocument();
  });
});
