import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
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
    const longText = "a".repeat(201);
    render(<ChatMessageBubble role="assistant" content={longText} />);

    expect(screen.getByText("a".repeat(200))).toBeInTheDocument();
    expect(screen.getByText("...")).toBeInTheDocument();
    expect(screen.queryByText(longText)).not.toBeInTheDocument();

    const showMoreBtn = screen.getByRole("button", { name: /show more/i });
    await user.click(showMoreBtn);

    expect(screen.getByText(longText)).toBeInTheDocument();
    expect(screen.queryByText("...")).not.toBeInTheDocument();

    const showLessBtn = screen.getByRole("button", { name: /show less/i });
    await user.click(showLessBtn);

    expect(screen.getByText("a".repeat(200))).toBeInTheDocument();
    expect(screen.getByText("...")).toBeInTheDocument();
  });

  it("does not collapse long messages if isLast is true", () => {
    const longText = "a".repeat(201);
    render(
      <ChatMessageBubble role="assistant" content={longText} isLast={true} />,
    );

    expect(screen.getByText(longText)).toBeInTheDocument();
    expect(screen.queryByText("...")).not.toBeInTheDocument();
  });

  it("renders assistant response time when present", () => {
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
});
