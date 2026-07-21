import { render, screen, waitFor, act } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import AddEditVocabularyModal from "./AddEditVocabularyModal";
import { VOCABULARY_IMPROVEMENT_MODES } from "../constants";
import { AuthProvider } from "../context/AuthContext";

// Mock the useVocabulary hook
vi.mock("../hooks/useVocabulary", () => ({
  improveVocabularyItem: vi.fn(),
}));

import { improveVocabularyItem } from "../hooks/useVocabulary";

const mockImproveVocabularyItem = vi.mocked(improveVocabularyItem);

// Mock the useApi hook
vi.mock("../utils/api", () => ({
  useApi: vi.fn(() => ({
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
    delete: vi.fn(),
    patch: vi.fn(),
    apiClient: vi.fn(),
  })),
}));

describe("AddEditVocabularyModal", () => {
  const mockOnClose = vi.fn();
  const mockOnSave = vi.fn();
  const mockOnDelete = vi.fn();
  const mockOnLookup = vi.fn();
  const mockOnLookupFound = vi.fn();

  const defaultProps = {
    open: true,
    item: null,
    onClose: mockOnClose,
    onSave: mockOnSave,
    onDelete: mockOnDelete,
    onLookup: mockOnLookup,
    onLookupFound: mockOnLookupFound,
  };

  const renderWithAuthProvider = (component: React.ReactElement) => {
    return render(
      <AuthProvider>
        {component}
      </AuthProvider>
    );
  };

  beforeEach(() => {
    mockOnClose.mockClear();
    mockOnSave.mockClear();
    mockOnDelete.mockClear();
    mockOnLookup.mockClear();
    mockOnLookupFound.mockClear();
    mockImproveVocabularyItem.mockClear();
  });

  it("renders the modal for adding a new item", () => {
    renderWithAuthProvider(<AddEditVocabularyModal {...defaultProps} />);

    expect(screen.getByText("Add a vocabulary item")).toBeInTheDocument();
    expect(screen.getByLabelText("Swedish Word/Phrase")).toBeInTheDocument();
    expect(screen.getByLabelText("English Translation")).toBeInTheDocument();
    expect(
      screen.getByLabelText("Example Phrase (Optional)")
    ).toBeInTheDocument();
    expect(screen.getByRole("checkbox", { name: "In Learning" })).toBeInTheDocument();
    expect(screen.getByRole("group", { name: "Priority (0-9)" })).toBeInTheDocument();
    expect(screen.getByText("0 = sooner · 9 = later")).toBeInTheDocument();
  });

  it("renders the modal for editing an existing item", () => {
    const existingItem = {
      id: 1,
      user_id: 1,
      word_phrase: "hej",
      translation: "hello",
      example_phrase: "Hej, hur mår du?",
      extra_info: null,
      in_learn: true,
      priority_learn: 5,
      last_learned: null,
      created_at: "2023-10-27T10:00:00Z",
    };

    renderWithAuthProvider(<AddEditVocabularyModal {...defaultProps} item={existingItem} />);

    expect(screen.getByText("Edit vocabulary item")).toBeInTheDocument();
    expect(screen.getByDisplayValue("hej")).toBeInTheDocument();
    expect(screen.getByDisplayValue("hello")).toBeInTheDocument();
    expect(screen.getByDisplayValue("Hej, hur mår du?")).toBeInTheDocument();
  });

  it("calls onClose when close button is clicked", async () => {
    const user = userEvent.setup();
    renderWithAuthProvider(<AddEditVocabularyModal {...defaultProps} />);

    const closeButton = screen.getByRole("button", { name: "Close vocabulary dialog" });
    await user.click(closeButton);

    expect(mockOnClose).toHaveBeenCalledTimes(1);
  });

  it("calls onClose when Cancel button is clicked", async () => {
    const user = userEvent.setup();
    renderWithAuthProvider(<AddEditVocabularyModal {...defaultProps} />);

    const cancelButton = screen.getByRole("button", { name: "Cancel" });
    await user.click(cancelButton);

    expect(mockOnClose).toHaveBeenCalledTimes(1);
  });


  it("hides lookup until a word phrase is available", () => {
    renderWithAuthProvider(<AddEditVocabularyModal {...defaultProps} />);

    expect(screen.queryByTitle("Look up existing word")).not.toBeInTheDocument();
  });

  it("looks up the trimmed word and shows a found notification", async () => {
    const user = userEvent.setup();
    mockOnLookup.mockResolvedValue({
      id: 7,
      user_id: 1,
      word_phrase: "hej",
      translation: "hello",
      example_phrase: "Hej!",
      extra_info: "interjection",
      in_learn: true,
      priority_learn: 3,
      last_learned: null,
      created_at: "2023-10-27T10:00:00Z",
    });

    renderWithAuthProvider(<AddEditVocabularyModal {...defaultProps} />);

    await user.type(screen.getByLabelText("Swedish Word/Phrase"), "  hej  ");
    await user.click(screen.getByTitle("Look up existing word"));

    await waitFor(() => {
      expect(mockOnLookup).toHaveBeenCalledWith("hej");
      expect(
        screen.getByText("Found existing word: hej. Editing saved entry.")
      ).toBeInTheDocument();
      expect(mockOnLookupFound).toHaveBeenCalledWith(
        expect.objectContaining({ id: 7, word_phrase: "hej" })
      );
    });
  });



  it("ignores a lookup result after the modal is closed", async () => {
    const user = userEvent.setup();
    let resolveLookup: (item: unknown) => void = () => {};
    mockOnLookup.mockReturnValue(
      new Promise((resolve) => {
        resolveLookup = resolve;
      })
    );

    renderWithAuthProvider(<AddEditVocabularyModal {...defaultProps} />);

    await user.type(screen.getByLabelText("Swedish Word/Phrase"), "hej");
    await user.click(screen.getByTitle("Look up existing word"));
    await user.click(screen.getByRole("button", { name: "Cancel" }));

    await act(async () => {
      resolveLookup({
        id: 7,
        user_id: 1,
        word_phrase: "hej",
        translation: "hello",
        example_phrase: "Hej!",
        extra_info: null,
        in_learn: true,
        priority_learn: 3,
        last_learned: null,
        created_at: "2023-10-27T10:00:00Z",
      });
    });

    expect(mockOnClose).toHaveBeenCalledTimes(1);
    expect(
      screen.queryByText("Found existing word: hej. Editing saved entry.")
    ).not.toBeInTheDocument();
    expect(mockOnLookupFound).not.toHaveBeenCalled();
  });

  it("keeps add mode and shows a not-found notification when lookup misses", async () => {
    const user = userEvent.setup();
    mockOnLookup.mockResolvedValue(null);

    renderWithAuthProvider(<AddEditVocabularyModal {...defaultProps} />);

    await user.type(screen.getByLabelText("Swedish Word/Phrase"), "nytt");
    await user.click(screen.getByTitle("Look up existing word"));

    await waitFor(() => {
      expect(screen.getByText("No existing word found.")).toBeInTheDocument();
    });
    expect(screen.getByText("Add a vocabulary item")).toBeInTheDocument();
  });

  it("shows an inline error when lookup fails", async () => {
    const user = userEvent.setup();
    mockOnLookup.mockRejectedValue(new Error("Lookup failed"));

    renderWithAuthProvider(<AddEditVocabularyModal {...defaultProps} />);

    await user.type(screen.getByLabelText("Swedish Word/Phrase"), "hej");
    await user.click(screen.getByTitle("Look up existing word"));

    await waitFor(() => {
      expect(screen.getByText("Lookup failed")).toBeInTheDocument();
    });
  });

  it("fills all fields when Fill All icon button is clicked", async () => {
    const user = userEvent.setup();
    mockImproveVocabularyItem.mockResolvedValue({
      translation: "hello",
      example_phrase: "Hej, hur mår du?",
      extra_info: "en-word, noun, base form: hej",
    });

    renderWithAuthProvider(<AddEditVocabularyModal {...defaultProps} />);

    // Fill word phrase first
    const wordInput = screen.getByLabelText("Swedish Word/Phrase");
    await user.type(wordInput, "hej");

    // Click Fill All button (AutoFixHigh icon)
    const fillAllButton = screen.getByTitle("Fill All");
    await user.click(fillAllButton);

    await waitFor(() => {
      expect(mockImproveVocabularyItem).toHaveBeenCalledWith(
        expect.any(Object),
        "hej",
        VOCABULARY_IMPROVEMENT_MODES.ALL_FIELDS
      );
    });

    // Check that fields are filled
    await waitFor(() => {
      expect(screen.getByDisplayValue("hello")).toBeInTheDocument();
      expect(screen.getByDisplayValue("Hej, hur mår du?")).toBeInTheDocument();
      expect(screen.getByDisplayValue("en-word, noun, base form: hej")).toBeInTheDocument();
    });
  });

  it("fills example phrase when Fill Example icon button is clicked", async () => {
    const user = userEvent.setup();
    mockImproveVocabularyItem.mockResolvedValue({
      example_phrase: "Hej, hur mår du?",
    });

    renderWithAuthProvider(<AddEditVocabularyModal {...defaultProps} />);

    // Fill word phrase first
    const wordInput = screen.getByLabelText("Swedish Word/Phrase");
    await user.type(wordInput, "hej");

    // Click Fill Example button (AutoFixNormal icon)
    const fillExampleButton = screen.getByTitle("Fill Example");
    await user.click(fillExampleButton);

    await waitFor(() => {
      expect(mockImproveVocabularyItem).toHaveBeenCalledWith(
        expect.any(Object),
        "hej",
        VOCABULARY_IMPROVEMENT_MODES.EXAMPLE_ONLY
      );
    });

    // Check that example phrase is filled
    await waitFor(() => {
      expect(screen.getByDisplayValue("Hej, hur mår du?")).toBeInTheDocument();
    });
  });

  it("hides suggestion actions until a word phrase is available", () => {
    renderWithAuthProvider(<AddEditVocabularyModal {...defaultProps} />);

    expect(screen.queryByTitle("Fill All")).not.toBeInTheDocument();
    expect(screen.queryByTitle("Fill Example")).not.toBeInTheDocument();
    expect(screen.queryByTitle("Fill Extra Info")).not.toBeInTheDocument();
  });

  it("replaces suggestion actions with progress while improving", async () => {
    const user = userEvent.setup();
    mockImproveVocabularyItem.mockImplementation(() => new Promise(() => {})); // Never resolves

    renderWithAuthProvider(<AddEditVocabularyModal {...defaultProps} />);

    // Fill word phrase first
    const wordInput = screen.getByLabelText("Swedish Word/Phrase");
    await user.type(wordInput, "hej");

    // Click Fill All button
    const fillAllButton = screen.getByTitle("Fill All");
    await user.click(fillAllButton);

    // Actions should not remain as ugly disabled controls while improving.
    await waitFor(() => {
      expect(screen.queryByTitle("Fill All")).not.toBeInTheDocument();
      expect(screen.queryByTitle("Fill Example")).not.toBeInTheDocument();
      expect(screen.getByText("Building suggestions…")).toBeInTheDocument();
    });
  });

  it("ignores an AI result after the modal is closed", async () => {
    const user = userEvent.setup();
    let resolveImprove: (result: {
      translation: string;
      example_phrase: string;
      extra_info: string;
    }) => void = () => {};
    mockImproveVocabularyItem.mockReturnValue(
      new Promise((resolve) => {
        resolveImprove = resolve;
      })
    );

    renderWithAuthProvider(<AddEditVocabularyModal {...defaultProps} />);

    await user.type(screen.getByLabelText("Swedish Word/Phrase"), "hej");
    await user.click(screen.getByTitle("Fill All"));
    await user.click(screen.getByRole("button", { name: "Cancel" }));

    await act(async () => {
      resolveImprove({
        translation: "hello",
        example_phrase: "Hej, hur mår du?",
        extra_info: "interjection",
      });
    });

    expect(mockOnClose).toHaveBeenCalledTimes(1);
    expect(screen.queryByDisplayValue("hello")).not.toBeInTheDocument();
    expect(screen.queryByDisplayValue("Hej, hur mår du?")).not.toBeInTheDocument();
    expect(screen.queryByDisplayValue("interjection")).not.toBeInTheDocument();
  });

  it("ignores an AI error after the modal is closed", async () => {
    const user = userEvent.setup();
    let rejectImprove: (reason?: unknown) => void = () => {};
    mockImproveVocabularyItem.mockReturnValue(
      new Promise((_resolve, reject) => {
        rejectImprove = reject;
      })
    );

    renderWithAuthProvider(<AddEditVocabularyModal {...defaultProps} />);

    await user.type(screen.getByLabelText("Swedish Word/Phrase"), "hej");
    await user.click(screen.getByTitle("Fill All"));
    await user.click(screen.getByRole("button", { name: "Cancel" }));

    await act(async () => {
      rejectImprove(new Error("Improve failed after close"));
    });

    expect(mockOnClose).toHaveBeenCalledTimes(1);
    expect(screen.queryByText("Improve failed after close")).not.toBeInTheDocument();
  });

  it("calls onSave when Add to vocabulary is clicked with valid data", async () => {
    const user = userEvent.setup();
    renderWithAuthProvider(<AddEditVocabularyModal {...defaultProps} />);

    const wordInput = screen.getByLabelText("Swedish Word/Phrase");
    const translationInput = screen.getByLabelText("English Translation");
    const exampleInput = screen.getByLabelText("Example Phrase (Optional)");

    await user.type(wordInput, "hej");
    await user.type(translationInput, "hello");
    await user.type(exampleInput, "Hej, hur mår du?");

    const saveButton = screen.getByRole("button", { name: "Add to vocabulary" });
    await user.click(saveButton);

    expect(mockOnSave).toHaveBeenCalledWith({
      word_phrase: "hej",
      translation: "hello",
      example_phrase: "Hej, hur mår du?",
      extra_info: null,
      in_learn: true,
      priority_learn: 5,
    });
  });

  it("submits the form when Enter is pressed in the translation field", async () => {
    const user = userEvent.setup();
    renderWithAuthProvider(<AddEditVocabularyModal {...defaultProps} />);

    await user.type(screen.getByLabelText("Swedish Word/Phrase"), "hej");
    await user.type(screen.getByLabelText("English Translation"), "hello");
    await user.keyboard("{Enter}");

    await waitFor(() => {
      expect(mockOnSave).toHaveBeenCalledWith({
        word_phrase: "hej",
        translation: "hello",
        example_phrase: null,
        extra_info: null,
        in_learn: true,
        priority_learn: 5,
      });
    });
  });

  it("replaces save with progress while pending and restores it after completion", async () => {
    const user = userEvent.setup();
    let resolveSave: () => void = () => {};
    mockOnSave.mockReturnValue(
      new Promise<void>((resolve) => {
        resolveSave = resolve;
      })
    );

    renderWithAuthProvider(<AddEditVocabularyModal {...defaultProps} />);

    await user.type(screen.getByLabelText("Swedish Word/Phrase"), "hej");
    await user.type(screen.getByLabelText("English Translation"), "hello");
    await user.click(screen.getByRole("button", { name: "Add to vocabulary" }));

    expect(screen.queryByRole("button", { name: "Add to vocabulary" })).not.toBeInTheDocument();
    expect(screen.getByText("Saving…")).toBeInTheDocument();
    expect(mockOnSave).toHaveBeenCalledTimes(1);

    await act(async () => {
      resolveSave();
    });

    await waitFor(() => {
      expect(
        screen.getByRole("button", { name: "Add to vocabulary" })
      ).toBeEnabled();
    });
  });

  it("calls onSave with in_learn: false when checkbox is unchecked", async () => {
    const user = userEvent.setup();
    renderWithAuthProvider(<AddEditVocabularyModal {...defaultProps} />);

    const wordInput = screen.getByLabelText("Swedish Word/Phrase");
    const translationInput = screen.getByLabelText("English Translation");
    const checkbox = screen.getByRole("checkbox", { name: "In Learning" });

    await user.type(wordInput, "hej");
    await user.type(translationInput, "hello");
    await user.click(checkbox); // Uncheck the checkbox

    const saveButton = screen.getByRole("button", { name: "Add to vocabulary" });
    await user.click(saveButton);

    expect(mockOnSave).toHaveBeenCalledWith({
      word_phrase: "hej",
      translation: "hello",
      example_phrase: null,
      extra_info: null,
      in_learn: false,
      priority_learn: 5,
    });
  });

  it("calls onSave with selected numeric priority", async () => {
    const user = userEvent.setup();
    renderWithAuthProvider(<AddEditVocabularyModal {...defaultProps} />);

    const wordInput = screen.getByLabelText("Swedish Word/Phrase");
    const translationInput = screen.getByLabelText("English Translation");
    await user.type(wordInput, "hej");
    await user.type(translationInput, "hello");
    await user.click(screen.getByRole("button", { name: "Priority 2" }));

    const saveButton = screen.getByRole("button", { name: "Add to vocabulary" });
    await user.click(saveButton);

    expect(mockOnSave).toHaveBeenCalledWith({
      word_phrase: "hej",
      translation: "hello",
      example_phrase: null,
      extra_info: null,
      in_learn: true,
      priority_learn: 2,
    });
  });

  it("hides save and explains what is missing when required fields are empty", () => {
    renderWithAuthProvider(<AddEditVocabularyModal {...defaultProps} />);

    expect(screen.queryByRole("button", { name: "Add to vocabulary" })).not.toBeInTheDocument();
    expect(screen.getByText("Add a word and translation to continue.")).toBeInTheDocument();
    expect(mockOnSave).not.toHaveBeenCalled();
  });

  it("shows error message when save fails", async () => {
    const user = userEvent.setup();
    mockOnSave.mockRejectedValue(new Error("Save failed"));

    renderWithAuthProvider(<AddEditVocabularyModal {...defaultProps} />);

    const wordInput = screen.getByLabelText("Swedish Word/Phrase");
    const translationInput = screen.getByLabelText("English Translation");

    await user.type(wordInput, "hej");
    await user.type(translationInput, "hello");

    const saveButton = screen.getByRole("button", { name: "Add to vocabulary" });
    await user.click(saveButton);

    await waitFor(() => {
      expect(screen.getByText("Save failed")).toBeInTheDocument();
    });
    expect(
      screen.getByRole("button", { name: "Add to vocabulary" })
    ).toBeEnabled();
  });

  it("shows error message when improve vocabulary fails", async () => {
    const user = userEvent.setup();
    mockImproveVocabularyItem.mockRejectedValue(new Error("Improve failed"));

    renderWithAuthProvider(<AddEditVocabularyModal {...defaultProps} />);

    const wordInput = screen.getByLabelText("Swedish Word/Phrase");
    await user.type(wordInput, "hej");

    const fillAllButton = screen.getByTitle("Fill All");
    await user.click(fillAllButton);

    await waitFor(() => {
      expect(screen.getByText("Improve failed")).toBeInTheDocument();
    });
  });

  it("shows Delete button when editing existing item", () => {
    const existingItem = {
      id: 1,
      user_id: 1,
      word_phrase: "hej",
      translation: "hello",
      example_phrase: null,
      extra_info: null,
      in_learn: false,
      priority_learn: 9,
      last_learned: null,
      created_at: "2023-10-27T10:00:00Z",
    };

    renderWithAuthProvider(<AddEditVocabularyModal {...defaultProps} item={existingItem} />);

    expect(screen.getByRole("button", { name: "Delete" })).toBeInTheDocument();
  });

  it("calls onDelete when Delete button is clicked", async () => {
    const user = userEvent.setup();
    const existingItem = {
      id: 1,
      user_id: 1,
      word_phrase: "hej",
      translation: "hello",
      example_phrase: null,
      extra_info: null,
      in_learn: false,
      priority_learn: 9,
      last_learned: null,
      created_at: "2023-10-27T10:00:00Z",
    };

    renderWithAuthProvider(<AddEditVocabularyModal {...defaultProps} item={existingItem} />);

    const deleteButton = screen.getByRole("button", { name: "Delete" });
    await user.click(deleteButton);

    expect(mockOnDelete).toHaveBeenCalledTimes(1);
  });

  it("toggles in learning checkbox", async () => {
    const user = userEvent.setup();
    renderWithAuthProvider(<AddEditVocabularyModal {...defaultProps} />);

    const checkbox = screen.getByRole("checkbox", { name: "In Learning" });
    expect(checkbox).toBeChecked(); // Now defaults to true

    await user.click(checkbox);
    expect(checkbox).not.toBeChecked();

    await user.click(checkbox);
    expect(checkbox).toBeChecked();
  });
});
