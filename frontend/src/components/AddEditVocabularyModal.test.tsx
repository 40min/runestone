import { render, screen, waitFor } from "@testing-library/react";
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
  useApi: vi.fn(() => vi.fn()), // Return a mock API function
}));

describe("AddEditVocabularyModal", () => {
  const mockOnClose = vi.fn();
  const mockOnSave = vi.fn();
  const mockOnDelete = vi.fn();

  const defaultProps = {
    open: true,
    item: null,
    onClose: mockOnClose,
    onSave: mockOnSave,
    onDelete: mockOnDelete,
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
    mockImproveVocabularyItem.mockClear();
  });

  it("renders the modal for adding a new item", () => {
    renderWithAuthProvider(<AddEditVocabularyModal {...defaultProps} />);

    expect(screen.getByText("Add Vocabulary Item")).toBeInTheDocument();
    expect(screen.getByLabelText("Swedish Word/Phrase")).toBeInTheDocument();
    expect(screen.getByLabelText("English Translation")).toBeInTheDocument();
    expect(
      screen.getByLabelText("Example Phrase (Optional)")
    ).toBeInTheDocument();
    expect(screen.getByText("In Learning")).toBeInTheDocument();
  });

  it("renders the modal for editing an existing item", () => {
    const existingItem = {
      id: 1,
      user_id: 1,
      word_phrase: "hej",
      translation: "hello",
      example_phrase: "Hej, hur mår du?",
      in_learn: true,
      last_learned: null,
      created_at: "2023-10-27T10:00:00Z",
    };

    renderWithAuthProvider(<AddEditVocabularyModal {...defaultProps} item={existingItem} />);

    expect(screen.getByText("Edit Vocabulary Item")).toBeInTheDocument();
    expect(screen.getByDisplayValue("hej")).toBeInTheDocument();
    expect(screen.getByDisplayValue("hello")).toBeInTheDocument();
    expect(screen.getByDisplayValue("Hej, hur mår du?")).toBeInTheDocument();
  });

  it("calls onClose when close button is clicked", async () => {
    const user = userEvent.setup();
    renderWithAuthProvider(<AddEditVocabularyModal {...defaultProps} />);

    const closeButton = screen.getByRole("button", { name: /×/ });
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
      expect(mockImproveVocabularyItem).toHaveBeenCalledWith(expect.any(Function), "hej", VOCABULARY_IMPROVEMENT_MODES.ALL_FIELDS);
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
      expect(mockImproveVocabularyItem).toHaveBeenCalledWith(expect.any(Function), "hej", VOCABULARY_IMPROVEMENT_MODES.EXAMPLE_ONLY);
    });

    // Check that example phrase is filled
    await waitFor(() => {
      expect(screen.getByDisplayValue("Hej, hur mår du?")).toBeInTheDocument();
    });
  });

  it("disables fill buttons when word phrase is empty", () => {
    renderWithAuthProvider(<AddEditVocabularyModal {...defaultProps} />);

    const fillAllButton = screen.getByTitle("Fill All");
    const fillExampleButton = screen.getByTitle("Fill Example");

    expect(fillAllButton).toBeDisabled();
    expect(fillExampleButton).toBeDisabled();
  });

  it("disables fill buttons when improving", async () => {
    const user = userEvent.setup();
    mockImproveVocabularyItem.mockImplementation(() => new Promise(() => {})); // Never resolves

    renderWithAuthProvider(<AddEditVocabularyModal {...defaultProps} />);

    // Fill word phrase first
    const wordInput = screen.getByLabelText("Swedish Word/Phrase");
    await user.type(wordInput, "hej");

    // Click Fill All button
    const fillAllButton = screen.getByTitle("Fill All");
    await user.click(fillAllButton);

    // Buttons should be disabled while improving
    await waitFor(() => {
      expect(fillAllButton).toBeDisabled();
      expect(screen.getByTitle("Fill Example")).toBeDisabled();
    });
  });

  it("calls onSave when Add Item button is clicked with valid data", async () => {
    const user = userEvent.setup();
    renderWithAuthProvider(<AddEditVocabularyModal {...defaultProps} />);

    const wordInput = screen.getByLabelText("Swedish Word/Phrase");
    const translationInput = screen.getByLabelText("English Translation");
    const exampleInput = screen.getByLabelText("Example Phrase (Optional)");

    await user.type(wordInput, "hej");
    await user.type(translationInput, "hello");
    await user.type(exampleInput, "Hej, hur mår du?");

    const saveButton = screen.getByRole("button", { name: "Add Item" });
    await user.click(saveButton);

    expect(mockOnSave).toHaveBeenCalledWith({
      word_phrase: "hej",
      translation: "hello",
      example_phrase: "Hej, hur mår du?",
      extra_info: null,
      in_learn: true,
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

    const saveButton = screen.getByRole("button", { name: "Add Item" });
    await user.click(saveButton);

    expect(mockOnSave).toHaveBeenCalledWith({
      word_phrase: "hej",
      translation: "hello",
      example_phrase: null,
      extra_info: null,
      in_learn: false,
    });
  });

  it("does not call onSave when required fields are empty", () => {
    renderWithAuthProvider(<AddEditVocabularyModal {...defaultProps} />);

    const saveButton = screen.getByRole("button", { name: "Add Item" });

    // Button should be disabled when required fields are empty
    expect(saveButton).toBeDisabled();
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

    const saveButton = screen.getByRole("button", { name: "Add Item" });
    await user.click(saveButton);

    await waitFor(() => {
      expect(screen.getByText("Save failed")).toBeInTheDocument();
    });
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
      in_learn: false,
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
      in_learn: false,
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
