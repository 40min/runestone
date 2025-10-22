import React, { useState, useEffect } from "react";
import { Box, Typography, Snackbar, Alert, IconButton } from "@mui/material";
import type { AlertColor } from "@mui/material";
import { Copy, Save } from "lucide-react";
import { ContentCopy } from "@mui/icons-material";
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
  swedish: string;
  english: string;
  example_phrase?: string;
  extra_info?: string;
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
  saveVocabulary: (vocabulary: VocabularyItem[], enrich: boolean) => Promise<void>;
}

const ResultsDisplay: React.FC<ResultsDisplayProps> = ({
  ocrResult,
  analysisResult,
  resourcesResult,
  error,
  saveVocabulary,
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
  const [checkedItems, setCheckedItems] = useState<boolean[]>(() =>
    analysisResult
      ? new Array(analysisResult.vocabulary.length).fill(false)
      : []
  );
  const [enrichVocabulary, setEnrichVocabulary] = useState(true);
  const [copyButtonText, setCopyButtonText] = useState("Copy");

  useEffect(() => {
    if (analysisResult) {
      setCheckedItems(new Array(analysisResult.vocabulary.length).fill(false));
    }
  }, [analysisResult]);

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

    const checkedVocab = analysisResult.vocabulary.filter(
      (_, index) => checkedItems[index]
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
        document.execCommand("copy");
        document.body.removeChild(textArea);
        setSnackbar({
          open: true,
          message: "Selected vocabulary copied to clipboard!",
          severity: "success",
        });
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

  const handleCheckboxChange = (index: number) => {
    const newCheckedItems = [...checkedItems];
    newCheckedItems[index] = !newCheckedItems[index];
    setCheckedItems(newCheckedItems);
  };

  const handleCheckAll = () => {
    if (!analysisResult) return;
    const allChecked = checkedItems.every(Boolean);
    const newCheckedItems = new Array(analysisResult.vocabulary.length).fill(
      !allChecked
    );
    setCheckedItems(newCheckedItems);
  };

  const handleSaveVocabulary = async () => {
    if (!analysisResult) return;

    const checkedVocab = analysisResult.vocabulary.filter(
      (_, index) => checkedItems[index]
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
                <Box sx={{ display: "flex", justifyContent: "flex-end", mb: 2 }}>
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
                    dangerouslySetInnerHTML={{ __html: parseMarkdown(ocrResult.text) }}
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
              {analysisResult && analysisResult.vocabulary.length > 0 && (
                <Box sx={{ display: "flex", gap: 2, alignItems: "center" }}>
                  <Box sx={{ display: "flex", alignItems: "center", gap: 1 }}>
                    <StyledCheckbox
                      checked={enrichVocabulary}
                      onChange={setEnrichVocabulary}
                    />
                    <Typography sx={{ color: "white" }}>Enrich with grammar info</Typography>
                  </Box>
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
              )}
            </Box>
            {analysisResult && (
              <Box sx={{ mt: 4 }}>
                <Box
                  sx={{ display: "flex", alignItems: "center", gap: 1, mb: 2 }}
                >
                  <StyledCheckbox
                    checked={checkedItems.every(Boolean)}
                    indeterminate={
                      checkedItems.some(Boolean) && !checkedItems.every(Boolean)
                    }
                    onChange={handleCheckAll}
                  />
                </Box>
                <DataTable
                  columns={[
                    {
                      key: "select",
                      label: "Select",
                      render: (_, __, index) => (
                        <StyledCheckbox
                          checked={checkedItems[index] || false}
                          onChange={() => handleCheckboxChange(index)}
                        />
                      ),
                    },
                    { key: "swedish", label: "Swedish" },
                    { key: "english", label: "English" },
                    {
                      key: "example_phrase",
                      label: "Example Phrase",
                      render: (value) => (value as string) || "—",
                    },
                  ]}
                  data={
                    analysisResult.vocabulary as unknown as Record<
                      string,
                      unknown
                    >[]
                  }
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
