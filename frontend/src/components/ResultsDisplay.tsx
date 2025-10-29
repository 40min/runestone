import React, { useState, useEffect, useMemo } from "react";
import { Box, Typography, Snackbar, Alert, IconButton } from "@mui/material";
import type { AlertColor } from "@mui/material";
import { Copy, Save } from "lucide-react";
import { ContentCopy } from "@mui/icons-material";
import { v4 as uuidv4 } from "uuid"; // Import uuid
import {
  CustomButton,
  ContentCard,
  ErrorAlert,
  SectionTitle,
  TabNavigation,
  StyledCheckbox,
  DataTable,
} from "./ui";
import { parseMarkdown } from "../utils/markdownParser";

// Helper function to enrich vocabulary items with a unique ID
const enrichVocabularyItems = (
  vocabulary: VocabularyItem[]
): EnrichedVocabularyItem[] => {
  return vocabulary.map((item) => ({
    ...item,
    id: item.id || uuidv4(), // Use existing ID or generate a new one
  }));
};

// Utility function to convert URLs in text to HTML links
const convertUrlsToLinks = (text: string): (string | React.ReactElement)[] => {
  if (!text) return [text];

  const urlRegex = /(https?:\/\/[^\s]+)/g;
  const parts = text.split(urlRegex);

  return parts.map((part, index) => {
    if (part.match(urlRegex)) {
      return (
        <a
          key={index}
          href={part}
          target="_blank"
          rel="noopener noreferrer"
          style={{ color: "var(--primary-color)", textDecoration: "underline" }}
        >
          {part}
        </a>
      );
    }
    return part;
  });
};

interface OCRResult {
  text: string;
  character_count: number;
}

interface GrammarFocus {
  topic: string;
  explanation: string;
  has_explicit_rules: boolean;
  rules?: string;
}

interface VocabularyItem {
  id?: string; // Make id optional in base interface
  swedish: string;
  english: string;
  example_phrase?: string;
  extra_info?: string;
  known?: boolean;
  [key: string]: unknown; // Add index signature
}

// New interface for enriched vocabulary items with a required ID
interface EnrichedVocabularyItem extends VocabularyItem {
  id: string;
}

interface ContentAnalysis {
  grammar_focus: GrammarFocus;
  vocabulary: VocabularyItem[];
}

interface ResultsDisplayProps {
  ocrResult: OCRResult | null;
  analysisResult: ContentAnalysis | null;
  resourcesResult: string | null;
  error: string | null;
  saveVocabulary: (
    vocabulary: EnrichedVocabularyItem[], // Use EnrichedVocabularyItem
    enrich: boolean
  ) => Promise<void>;
  onVocabularyUpdated?: (updatedVocabulary: EnrichedVocabularyItem[]) => void; // Optional callback
}

const ResultsDisplay: React.FC<ResultsDisplayProps> = ({
  ocrResult,
  analysisResult,
  resourcesResult,
  error,
  saveVocabulary,
  onVocabularyUpdated,
}) => {
  const availableTabs = [
    ocrResult && "ocr",
    analysisResult && "grammar",
    analysisResult && "vocabulary",
    resourcesResult && "extra_info",
  ].filter(Boolean) as string[];
  const [activeTab, setActiveTab] = useState(availableTabs[0] || "ocr");
  const [snackbar, setSnackbar] = useState<{
    open: boolean;
    message: string;
    severity: AlertColor;
  }>({
    open: false,
    message: "",
    severity: "success",
  });
  const [checkedItems, setCheckedItems] = useState<Map<string, boolean>>(
    () => new Map()
  );
  const [enrichVocabulary, setEnrichVocabulary] = useState(true);
  const [hideKnown, setHideKnown] = useState(false); // New state variable
  const [copyButtonText, setCopyButtonText] = useState("Copy");
  const [enrichedVocabulary, setEnrichedVocabulary] = useState<
    EnrichedVocabularyItem[]
  >([]);

  useEffect(() => {
    if (analysisResult?.vocabulary) {
      const newEnrichedVocabulary = enrichVocabularyItems(
        analysisResult.vocabulary
      );
      setEnrichedVocabulary(newEnrichedVocabulary);

      const initialCheckedItems = new Map<string, boolean>();
      newEnrichedVocabulary.forEach((item) =>
        initialCheckedItems.set(item.id, false)
      );
      setCheckedItems(initialCheckedItems);
    } else {
      setEnrichedVocabulary([]);
      setCheckedItems(new Map());
    }
  }, [analysisResult]);

  // Memoized filtered vocabulary list
  const filteredVocabulary = useMemo(
    () =>
      enrichedVocabulary.filter((item) => !hideKnown || !item.known),
    [enrichedVocabulary, hideKnown]
  );

  if (!ocrResult && !analysisResult && !resourcesResult) {
    if (error) {
      return (
        <Box sx={{ maxWidth: "64rem", mx: "auto", mt: 8 }}>
          <ErrorAlert message={error} />
        </Box>
      );
    }
    return null;
  }

  const handleCopyVocabulary = async () => {
    if (!analysisResult) return;

    const checkedVocab = filteredVocabulary.filter((item) =>
      checkedItems.get(item.id)
    );
    if (checkedVocab.length === 0) {
      setSnackbar({
        open: true,
        message: "No vocabulary items selected!",
        severity: "error",
      });
      return;
    }

    const vocabText = checkedVocab
      .map((item) => `${item.swedish} - ${item.english}`)
      .join("\n");

    try {
      // Check if clipboard API is available
      if (!navigator.clipboard) {
        // Fallback for older browsers
        const textArea = document.createElement("textarea");
        textArea.value = vocabText;
        document.body.appendChild(textArea);
        textArea.select();

        const successful = document.execCommand("copy");
        document.body.removeChild(textArea);

        if (successful) {
          setSnackbar({
            open: true,
            message: "Selected vocabulary copied to clipboard!",
            severity: "success",
          });
        } else {
          throw new Error("Fallback copy method failed");
        }
        return;
      }

      await navigator.clipboard.writeText(vocabText);
      setSnackbar({
        open: true,
        message: "Selected vocabulary copied to clipboard!",
        severity: "success",
      });
    } catch (err) {
      console.error("Failed to copy vocabulary: ", err);
      setSnackbar({
        open: true,
        message: "Failed to copy vocabulary. Please try again.",
        severity: "error",
      });
    }
  };

  const handleCheckboxChange = (id: string, checked: boolean) => {
    const newCheckedItems = new Map(checkedItems);
    newCheckedItems.set(id, checked);
    setCheckedItems(newCheckedItems);
  };

  const handleCheckAll = (checked: boolean) => {
    const newCheckedItems = new Map(checkedItems);
    filteredVocabulary.forEach((item) => newCheckedItems.set(item.id, checked));
    setCheckedItems(newCheckedItems);
  };

  const handleSaveVocabulary = async () => {
    if (!analysisResult) return;

    const checkedVocab = filteredVocabulary.filter((item) =>
      checkedItems.get(item.id)
    );
    if (checkedVocab.length === 0) {
      setSnackbar({
        open: true,
        message: "No vocabulary items selected!",
        severity: "error",
      });
      return;
    }

    try {
      await saveVocabulary(checkedVocab, enrichVocabulary);
      setSnackbar({
        open: true,
        message: enrichVocabulary
          ? "Selected vocabulary enriched and saved to database!"
          : "Selected vocabulary saved to database!",
        severity: "success",
      });

      // Update the local state for known items
      const updatedVocabulary = enrichedVocabulary.map((item) =>
        checkedItems.get(item.id) ? { ...item, known: true } : item
      );
      setEnrichedVocabulary(updatedVocabulary);

      // Clear checked items after saving
      setCheckedItems(new Map());

      // Call the optional callback to update parent component's state
      if (onVocabularyUpdated) {
        onVocabularyUpdated(updatedVocabulary);
      }
    } catch (err) {
      console.error("Failed to save vocabulary: ", err);
      setSnackbar({
        open: true,
        message: "Failed to save vocabulary. Please try again.",
        severity: "error",
      });
    }
  };

  const handleCopyOCRText = async () => {
    if (!ocrResult) return;

    try {
      // Check if clipboard API is available
      if (!navigator.clipboard) {
        // Fallback for older browsers or non-HTTPS contexts
        const textArea = document.createElement("textarea");
        textArea.value = ocrResult.text;
        document.body.appendChild(textArea);
        textArea.select();
        document.execCommand("copy");
        document.body.removeChild(textArea);
        setCopyButtonText("Copied!");
        setSnackbar({
          open: true,
          message: "OCR text copied to clipboard!",
          severity: "success",
        });
        setTimeout(() => setCopyButtonText("Copy"), 2000);
        return;
      }

      await navigator.clipboard.writeText(ocrResult.text);
      setCopyButtonText("Copied!");
      setSnackbar({
        open: true,
        message: "OCR text copied to clipboard!",
        severity: "success",
      });
      setTimeout(() => setCopyButtonText("Copy"), 2000);
    } catch (err) {
      console.error("Failed to copy OCR text: ", err);
      setSnackbar({
        open: true,
        message: "Failed to copy OCR text. Please try again.",
        severity: "error",
      });
    }
  };

  const tabs = [
    ocrResult && { id: "ocr", label: "OCR Text" },
    analysisResult && { id: "grammar", label: "Grammar" },
    analysisResult && { id: "vocabulary", label: "Vocabulary" },
    resourcesResult && { id: "extra_info", label: "Extra info" },
  ].filter(Boolean) as { id: string; label: string }[];

  return (
    <Box sx={{ py: 8 }}>
      <SectionTitle>Analysis Results</SectionTitle>

      {error && (
        <Box sx={{ mb: 4 }}>
          <ErrorAlert message={error} />
        </Box>
      )}

      <TabNavigation
        tabs={tabs}
        activeTab={activeTab}
        onTabChange={setActiveTab}
      />

      <Box sx={{ pt: 6 }}>
        {activeTab === "ocr" && (
          <Box>
            {!ocrResult && (
              <Typography sx={{ color: "#d1d5db", mb: 2 }}>
                The OCR text extracted from the image will be displayed here.
                This text can be edited and copied for further use.
              </Typography>
            )}
            {ocrResult && (
              <Box>
                <Box
                  sx={{ display: "flex", justifyContent: "flex-end", mb: 2 }}
                >
                  <IconButton
                    onClick={handleCopyOCRText}
                    sx={{
                      color: "var(--primary-color)",
                      "&:hover": {
                        backgroundColor: "rgba(255, 255, 255, 0.1)",
                      },
                    }}
                    title={copyButtonText}
                  >
                    <ContentCopy />
                  </IconButton>
                </Box>
                <ContentCard>
                  <Box
                    sx={{ color: "white" }}
                    className="markdown-content"
                    dangerouslySetInnerHTML={{
                      __html: parseMarkdown(ocrResult.text),
                    }}
                  />
                </ContentCard>
              </Box>
            )}
          </Box>
        )}

        {activeTab === "grammar" && (
          <Box>
            <SectionTitle>Grammar Analysis</SectionTitle>
            {analysisResult && (
              <Box
                sx={{ mt: 4, display: "flex", flexDirection: "column", gap: 4 }}
              >
                <ContentCard>
                  <Typography
                    sx={{
                      color: "var(--primary-color)",
                      fontWeight: "bold",
                      mb: 1,
                    }}
                  >
                    Topic:
                  </Typography>
                  <Typography sx={{ color: "white" }}>
                    {analysisResult.grammar_focus.topic}
                  </Typography>
                </ContentCard>
                <ContentCard>
                  <Typography
                    sx={{
                      color: "var(--primary-color)",
                      fontWeight: "bold",
                      mb: 1,
                    }}
                  >
                    Explanation:
                  </Typography>
                  <Typography sx={{ color: "white" }}>
                    {analysisResult.grammar_focus.explanation}
                  </Typography>
                </ContentCard>
                {analysisResult.grammar_focus.rules && (
                  <ContentCard>
                    <Typography
                      sx={{
                        color: "var(--primary-color)",
                        fontWeight: "bold",
                        mb: 1,
                      }}
                    >
                      Rules:
                    </Typography>
                    <Typography sx={{ color: "white", whiteSpace: "pre-wrap" }}>
                      {analysisResult.grammar_focus.rules}
                    </Typography>
                  </ContentCard>
                )}
                <ContentCard>
                  <Typography
                    sx={{
                      color: "var(--primary-color)",
                      fontWeight: "bold",
                      mb: 1,
                    }}
                  >
                    Has Explicit Rules:
                  </Typography>
                  <Typography sx={{ color: "white" }}>
                    {analysisResult.grammar_focus.has_explicit_rules
                      ? "Yes"
                      : "No"}
                  </Typography>
                </ContentCard>
              </Box>
            )}
          </Box>
        )}

        {activeTab === "vocabulary" && (
          <Box>
            <Box
              sx={{
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
                mb: 4,
              }}
            >
              <SectionTitle>Vocabulary Analysis</SectionTitle>
              {analysisResult && enrichedVocabulary.length > 0 && (
                <Box
                  sx={{
                    display: "flex",
                    flexDirection: "column",
                    alignItems: "flex-end",
                    gap: 1,
                  }}
                >
                  <Box sx={{ display: "flex", gap: 2 }}>
                    <CustomButton
                      variant="primary"
                      onClick={handleSaveVocabulary}
                      startIcon={<Save size={16} />}
                    >
                      Save to Database
                    </CustomButton>
                    <CustomButton
                      variant="primary"
                      onClick={handleCopyVocabulary}
                      startIcon={<Copy size={16} />}
                    >
                      Copy
                    </CustomButton>
                  </Box>
                  <Box
                    sx={{
                      display: "flex",
                      alignItems: "center",
                      gap: 1,
                      mt: 2,
                    }}
                  >
                    <StyledCheckbox
                      id="enrich-grammar-checkbox"
                      checked={enrichVocabulary}
                      onChange={(checked) => setEnrichVocabulary(checked)}
                    />
                    <Typography sx={{ color: "white" }}>
                      Enrich with grammar info
                    </Typography>
                  </Box>
                  {/* New checkbox for hiding known words */}
                  <Box
                    sx={{
                      display: "flex",
                      alignItems: "center",
                      gap: 1,
                      mt: 1,
                    }}
                  >
                    <StyledCheckbox
                      id="hide-known-words-checkbox"
                      checked={hideKnown}
                      onChange={(checked) => setHideKnown(checked)}
                    />
                    <Typography sx={{ color: "white" }}>
                      Hide known words
                    </Typography>
                  </Box>
                </Box>
              )}
            </Box>
            {analysisResult && (
              <Box sx={{ mt: 4 }}>
                <DataTable
                  selectable={true}
                  selectedItems={checkedItems}
                  onSelectionChange={handleCheckboxChange}
                  onSelectAll={handleCheckAll}
                  masterCheckboxId="vocabulary-master-checkbox"
                  rowCheckboxIdPrefix="vocabulary-item"
                  columns={[
                    { key: "swedish", label: "Swedish" },
                    { key: "english", label: "English" },
                    {
                      key: "example_phrase",
                      label: "Example Phrase",
                      render: (value) => (value as string) || "—",
                    },
                  ]}
                  data={filteredVocabulary}
                />
              </Box>
            )}
          </Box>
        )}

        {activeTab === "extra_info" && (
          <Box>
            <SectionTitle>Extra info</SectionTitle>
            {resourcesResult ? (
              <ContentCard>
                <Typography sx={{ color: "white", whiteSpace: "pre-wrap" }}>
                  {convertUrlsToLinks(resourcesResult)}
                </Typography>
              </ContentCard>
            ) : (
              <Typography sx={{ color: "#d1d5db" }}>
                Additional learning materials and resources will be displayed
                here.
              </Typography>
            )}
          </Box>
        )}
      </Box>
      <Snackbar
        open={snackbar.open}
        autoHideDuration={6000}
        onClose={() => setSnackbar({ ...snackbar, open: false })}
        anchorOrigin={{ vertical: "bottom", horizontal: "center" }}
      >
        <Alert
          onClose={() => setSnackbar({ ...snackbar, open: false })}
          severity={snackbar.severity}
          sx={{ width: "100%" }}
        >
          {snackbar.message}
        </Alert>
      </Snackbar>
    </Box>
  );
};

export default ResultsDisplay;
