Of course. Those are excellent points that refine the technical approach. Using a modern library like `httpx` is a great choice, and delegating the web search to the LLM agent simplifies the code and often yields better results.

Yes, this is entirely possible. Most advanced LLMs (including Gemini) support "tool use" or "function calling," where the model can be granted the ability to perform a Google search to answer a query. This is the modern and preferred way to handle this kind of task.

Here is the updated PRD incorporating your suggestions.

---

### **Product Requirements Document: Runestone (MVP)**

**Version:** 1.1 (Revised)
**Date:** 2025-08-21
**Author:** (Your Name/Handle Here)

### 1. Introduction & Vision

Runestone is a command-line interface (CLI) tool designed to accelerate the Swedish learning process for an independent student. By leveraging OCR and Large Language Models (LLMs), Runestone transforms a simple phone photo of a Swedish textbook page into a structured, digital study guide. The core problem it solves is the manual, time-consuming effort required to look up words, understand grammar rules, and find supplementary materials. This MVP aims to create an efficient bridge between a physical textbook and a digital, enriched learning experience.

### 2. Goals & Objectives

*   **Primary Goal:** To provide a quick, automated way to extract and understand the key learning components from a page of the "Rivstart" Swedish textbook.
*   **Key Objectives (MVP):**
    *   To accurately recognize and transcribe all Swedish text from an input image.
    *   To intelligently identify and separate grammar rules from exercises.
    *   To generate a concise vocabulary list (word bank) with English translations.
    *   To provide English translations and simple explanations for any identified grammar rules.
    *   To supplement the page's content with links to external, high-quality learning resources discovered via an agent-based web search.
    *   To deliver the output in a clean, human-readable format directly in the terminal.

### 3. Target Audience

For the MVP, the target user is the developer themself: a motivated, self-studying student of the Swedish language who is comfortable with using CLI tools.

### 4. Functional Requirements

#### FR-1: Image Input & OCR Processing
*   The script must accept a single command-line argument: the file path to an image (`.jpg`, `.png`, etc.).
*   The script will use an LLM with OCR capabilities (e.g., `gemini-2.5-flash` or similar) to read the image.
*   The system should be robust enough to handle typical photos taken with a smartphone, including minor variations in lighting, angle, and focus.

#### FR-2: Content Analysis
*   After OCR, an LLM (`gemini` family) will analyze the transcribed text.
*   The model must differentiate between distinct content blocks on the page, primarily:
    *   Grammar rule explanations.
    *   Exercises and examples.
    *   General text.
*   Images and graphical elements on the page should be ignored.

#### FR-3: Output Generation
The script will produce a single, formatted text output to the console, structured as follows:

*   **📖 Full Recognized Text:**
    *   This section will contain the complete, raw text extracted from the page for user reference.

*   **🎓 Grammar Focus:**
    *   **Scenario A (Explicit Rules):** If the LLM identifies a grammar rule box, it will be translated into English, followed by a short, simple explanation.
    *   **Scenario B (Implicit Rules):** If the page contains only exercises, the LLM will analyze the exercises to infer the grammatical topic being taught (e.g., "present tense verb conjugations," "definite vs. indefinite nouns"). It will then generate a short explanation of that rule.

*   **🔑 Word Bank:**
    *   The LLM will identify key vocabulary (nouns, verbs, adjectives, important phrases) from the page.
    *   This list will be presented in the format: `Svenska ord - English translation`.
    *   Multi-word phrases should be handled in the same format.

*   **🔗 Extra Resources:**
    *   The LLM will identify the core topic(s) of the page.
    *   **The LLM agent itself will be responsible for performing a web search** (e.g., via a `google_search` tool) to find relevant, high-quality explanatory links.
    *   **The model should be prompted to prioritize links from the following trusted sources if possible:**
        1.  `svenska.se`
        2.  `clozemaster.com/blog/`
        3.  `worddive.com/en/grammar/swedish-grammar/`
        4.  `kielibuusti.fi/en/learn-swedish/`
        5.  `swedishpod101.com/blog/`
    *   The output should be a list of 2-3 high-quality URLs.

### 5. User Interaction & Experience (UX)

*   The primary interaction will be via a CLI command.
*   **Example Usage:**
    ```bash
    runestone process /path/to/my/textbook_page.jpg
    ```
*   The output should be well-formatted with clear headings and emojis to enhance readability.

### 6. Technical Requirements

*   **Programming Language:** Python v.3.13
*   **Architecture:** The code must be organized in a modular/layered structure. Business logic should be separate from the CLI presentation layer. The use of functions and classes to encapsulate logic is required.
*   **Testing:** The project must include a test suite (e.g., using `pytest`) to ensure key components function correctly.
*   **CLI Framework:** Use the `Click` library for creating the command-line interface.
*   **Dependencies:**
    *   `google-generativeai` (or other relevant LLM SDK with tool-use support).
    *   `pytest` for testing.
    *   `httpx` can be used for any direct, simple API calls if needed, but is not required for web scraping.
    *   `rich` for nice output to console (emoji are welcomed)
    *   Use uv as package manager
    *   Use `pre-commit` for pre-commit hooks and common libs for style checking (flake8, black, isort)
    *   Write Makefile to run service commands like: 
        *   lint checking
        *   run tests
        *   install deps
        *   run the app

### 7. Error Handling

*   **File Not Found:** If the provided image path is invalid, the script should exit gracefully with an error message like: `Error: File not found at '/path/to/file.jpg'`.
*   **Recognition Failure:** If the LLM cannot recognize any meaningful text on the page, or determines it is not a Swedish textbook page, the script should output a simple, clear message: `Error: Could not recognise text on the page.` and terminate.

### 8. Performance Requirements

*   The end-to-end processing time for a single page (from command execution to final output) should be **under 10 seconds** on a standard internet connection. The primary bottleneck is expected to be the LLM and web search calls.

### 9. Assumptions

*   The input image is of a page from the "Rivstart" series of Swedish textbooks.
*   The user has an active and stable internet connection.
*   The user has the necessary API keys (e.g., for Gemini) configured in their environment, with permissions for tool use (i.e., search) enabled.

### 10. Future Scope (Out of Scope for MVP)

*   **GUI:** A graphical user interface for easier use.
*   **Batch Processing:** Ability to process multiple images or a whole PDF chapter at once.
*   **Interactive Mode:** A mode where the user can ask follow-up questions about the text.
*   **Anki Integration:** An option to export the word bank directly into an Anki flashcard deck (`.apkg` or `.csv` format).
*   **Support for other textbooks and languages.**