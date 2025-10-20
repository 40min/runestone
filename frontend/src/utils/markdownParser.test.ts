import { describe, it, expect } from "vitest";
import { parseMarkdown } from "./markdownParser";

describe("parseMarkdown", () => {
  describe("numbered lists with periods", () => {
    it("should parse standard numbered lists correctly", () => {
      const markdown = `1. First item
2. Second item
3. Third item`;

      const html = parseMarkdown(markdown);
      expect(html).toContain("<ol>");
      expect(html).toContain("<li>First item</li>");
      expect(html).toContain("<li>Second item</li>");
      expect(html).toContain("<li>Third item</li>");
    });

    it("should handle consecutive numbered lists starting with 1", () => {
      const markdown = `1. First list item
2. Second list item

1. New list first item
2. New list second item`;

      const html = parseMarkdown(markdown);
      // Should contain ordered list with all items
      expect(html).toContain("<ol>");
      expect(html).toContain("First list item");
      expect(html).toContain("Second list item");
      expect(html).toContain("New list first item");
      expect(html).toContain("New list second item");
    });
  });

  describe("numbered lists without periods", () => {
    it("should normalize numbered items without periods", () => {
      const markdown = `1 First item
2 Second item
3 Third item`;

      const html = parseMarkdown(markdown);
      expect(html).toContain("<ol>");
      expect(html).toContain("<li>First item</li>");
      expect(html).toContain("<li>Second item</li>");
      expect(html).toContain("<li>Third item</li>");
    });

    it("should handle Swedish text with numbered items without periods", () => {
      const markdown = `1 Jag vill gärna ha någon deckare.
2 Har vi frukt hemma?
3 Jag har ingen bil.`;

      const html = parseMarkdown(markdown);
      expect(html).toContain("<ol>");
      expect(html).toContain("<li>Jag vill gärna ha någon deckare.</li>");
      expect(html).toContain("Har vi frukt hemma?");
      expect(html).toContain("Jag har ingen bil.");
    });

    it("should handle mixed numbered items with and without periods", () => {
      const markdown = `1. First with period
2 Second without period
3. Third with period`;

      const html = parseMarkdown(markdown);
      expect(html).toContain("<ol>");
      expect(html).toContain("First with period");
      expect(html).toContain("Second without period");
      expect(html).toContain("Third with period");
    });
  });

  describe("bullet points after numbered lists", () => {
    it("should not merge bullet points into numbered list", () => {
      const markdown = `1 Jag vill gärna ha någon deckare.
- Har du någon cykel? - Ja, en röd mountainbike.
2 Har vi frukt hemma?`;

      const html = parseMarkdown(markdown);

      // The bullet should be escaped and not create a nested list
      expect(html).toContain("Jag vill gärna ha någon deckare.");
      expect(html).toContain("Har du någon cykel?");
      expect(html).toContain("Har vi frukt hemma?");
    });

    it("should handle dialogue with dashes after numbered items", () => {
      const markdown = `1. - Har du någon cykel? - Ja, en röd mountainbike.
2. - Har vi frukt hemma? - Ja, vi har några apelsiner.`;

      const html = parseMarkdown(markdown);
      expect(html).toContain("Har du någon cykel?");
      expect(html).toContain("Har vi frukt hemma?");
      // Should not create nested lists
      expect(html).not.toContain("<ul>");
    });
  });

  describe("complex real-world example", () => {
    it("should handle the FOKUS section correctly", () => {
      const markdown = `## FOKUS
1 Jag vill gärna ha någon deckare.
- Har du någon cykel? - Ja, en röd mountainbike.
2 - Har vi frukt hemma? - Ja, vi har några apelsiner.
3 Jag har ingen bil. = Jag har inte någon bil.
4 Jag vill inte ha någon ketchup.

1 Man använder någon / något / några när det när det inte spelar någon roll precis vad eller vilken.
2 Några kan betyda 2-3 stycken.
3 Ingen / inget / inga = inte någon / inte något / inte några.
4 I en mening med två verb (t.ex. hjälpverb och infinitiv) har man alltid inte någon, inte något, inte några.`;

      const html = parseMarkdown(markdown);

      // Should have heading
      expect(html).toContain("<h2>FOKUS</h2>");

      // Should contain ordered lists
      expect(html).toContain("<ol>");
      expect(html).toContain("<li>");

      // Should contain all the numbered items as proper list items
      expect(html).toContain("Jag vill gärna ha någon deckare");
      expect(html).toContain("Har du någon cykel?");
      expect(html).toContain("Har vi frukt hemma?");
      expect(html).toContain("Jag har ingen bil");
      expect(html).toContain("Man använder någon");
      expect(html).toContain("Några kan betyda 2-3 stycken");

      // Should not have nested unordered lists merged with ordered lists
      // The dialogue dashes should be escaped, preventing <ul> creation inside <ol>
      expect(html).not.toMatch(/<ol>[\s\S]*<ul>[\s\S]*<\/ul>[\s\S]*<\/ol>/);
    });

    it("should separate lists when line numbers decrease (e.g., 4→1)", () => {
      const markdown = `1 First item
2 Second item
3 Third item
4 Fourth item

1 New list first item
2 New list second item`;

      const html = parseMarkdown(markdown);

      // Should contain a horizontal rule separator between the two lists
      expect(html).toContain("<hr>");

      // Should contain both lists
      expect(html).toContain("First item");
      expect(html).toContain("Fourth item");
      expect(html).toContain("New list first item");
      expect(html).toContain("New list second item");
    });

    it("should separate lists on any decrease in line numbers (not just to 1)", () => {
      const markdown = `1 First
2 Second
3 Third
2 Restart at two
3 Continue at three`;

      const html = parseMarkdown(markdown);

      // Should contain a horizontal rule separator
      expect(html).toContain("<hr>");

      // Should contain all items
      expect(html).toContain("First");
      expect(html).toContain("Third");
      expect(html).toContain("Restart at two");
    });
  });

  describe("tables", () => {
    it("should parse tables correctly", () => {
      const markdown = `| En | Ett | Plural |
| --- | --- | --- |
| någon | något | några |
| ingen | inget | inga |`;

      const html = parseMarkdown(markdown);
      expect(html).toContain("<table>");
      expect(html).toContain("<thead>");
      expect(html).toContain("<tbody>");
      expect(html).toContain("någon");
      expect(html).toContain("något");
      expect(html).toContain("några");
    });
  });

  describe("headings", () => {
    it("should parse headings correctly", () => {
      const markdown = `# H1 Title
## H2 Title
### H3 Title`;

      const html = parseMarkdown(markdown);
      expect(html).toContain("<h1>H1 Title</h1>");
      expect(html).toContain("<h2>H2 Title</h2>");
      expect(html).toContain("<h3>H3 Title</h3>");
    });
  });

  describe("sanitization", () => {
    it("should sanitize dangerous HTML", () => {
      const markdown = `<script>alert('xss')</script>
<img src="x" onerror="alert('xss')">`;

      const html = parseMarkdown(markdown);
      expect(html).not.toContain("<script>");
      expect(html).not.toContain("onerror");
    });

    it("should allow safe HTML tags", () => {
      const markdown = `**bold** *italic* [link](https://example.com)`;

      const html = parseMarkdown(markdown);
      expect(html).toContain("<strong>bold</strong>");
      expect(html).toContain("<em>italic</em>");
      expect(html).toContain('<a href="https://example.com">link</a>');
    });
  });
});
