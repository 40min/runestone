import React, { useState, useEffect } from "react";
import { Box, Typography, Button, Snackbar, Alert, Checkbox } from "@mui/material";
import type { AlertColor } from "@mui/material";
import { Copy, AlertTriangle } from "lucide-react";

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
}

const ResultsDisplay: React.FC<ResultsDisplayProps> = ({
  ocrResult,
  analysisResult,
  resourcesResult,
  error,
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
    message: '',
    severity: 'success',
  });
  const [checkedItems, setCheckedItems] = useState<boolean[]>([]);

  useEffect(() => {
    if (analysisResult) {
      setCheckedItems(new Array(analysisResult.vocabulary.length).fill(true));
    }
  }, [analysisResult]);

  if (error) {
    return (
      <Box sx={{ maxWidth: "64rem", mx: "auto", mt: 8 }}>
        <Box
          sx={{
            backgroundColor: "rgba(220, 38, 38, 0.1)",
            border: "1px solid #dc2626",
            borderRadius: "0.75rem",
            p: 6,
          }}
        >
          <Box sx={{ display: "flex", alignItems: "flex-start" }}>
            <Box sx={{ flexShrink: 0 }}>
              <Box
                sx={{
                  width: 10,
                  height: 10,
                  backgroundColor: "rgba(220, 38, 38, 0.5)",
                  borderRadius: "50%",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                }}
              >
                <AlertTriangle size={20} style={{ color: "#ef4444" }} />
              </Box>
            </Box>
            <Box sx={{ ml: 4 }}>
              <Typography
                variant="body1"
                sx={{
                  fontSize: "1.125rem",
                  fontWeight: 600,
                  color: "#ef4444",
                  mb: 1,
                }}
              >
                Processing Error
              </Typography>
              <Box sx={{ color: "#dc2626" }}>
                <Typography>{error}</Typography>
              </Box>
            </Box>
          </Box>
        </Box>
      </Box>
    );
  }

  if (!ocrResult && !analysisResult && !resourcesResult) {
    return null;
  }

  const handleCopyVocabulary = async () => {
    if (!analysisResult) return;

    const checkedVocab = analysisResult.vocabulary.filter((_, index) => checkedItems[index]);
    if (checkedVocab.length === 0) {
      setSnackbar({ open: true, message: 'No vocabulary items selected!', severity: 'error' });
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
        document.execCommand('copy');
        document.body.removeChild(textArea);
        setSnackbar({ open: true, message: 'Selected vocabulary copied to clipboard!', severity: 'success' });
        return;
      }

      await navigator.clipboard.writeText(vocabText);
      setSnackbar({ open: true, message: 'Selected vocabulary copied to clipboard!', severity: 'success' });
    } catch (err) {
      console.error('Failed to copy vocabulary: ', err);
      setSnackbar({ open: true, message: 'Failed to copy vocabulary. Please try again.', severity: 'error' });
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
    const newCheckedItems = new Array(analysisResult.vocabulary.length).fill(!allChecked);
    setCheckedItems(newCheckedItems);
  };

  const tabs = [
    ocrResult && { id: "ocr", label: "OCR Text" },
    analysisResult && { id: "grammar", label: "Grammar" },
    analysisResult && { id: "vocabulary", label: "Vocabulary" },
    resourcesResult && { id: "extra_info", label: "Extra info" },
  ].filter(Boolean) as { id: string; label: string }[];

  return (
    <Box sx={{ py: 8 }}>
      <Typography
        variant="h4"
        sx={{ mb: 4, color: "white", fontWeight: "bold" }}
      >
        Analysis Results
      </Typography>

      <Box sx={{ borderBottom: "1px solid #4d3c63" }}>
        <Box sx={{ display: "flex", mb: "-1px", gap: 8 }}>
          {tabs.map((tab) => (
            <Button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              sx={{
                px: 1,
                py: 4,
                borderBottom:
                  activeTab === tab.id
                    ? "2px solid var(--primary-color)"
                    : "2px solid transparent",
                color:
                  activeTab === tab.id ? "var(--primary-color)" : "#9ca3af",
                fontWeight: "medium",
                fontSize: "0.875rem",
                textTransform: "none",
                "&:hover": {
                  color: "white",
                  borderBottomColor:
                    activeTab === tab.id ? "var(--primary-color)" : "#6b7280",
                },
                transition: "color 0.2s, border-color 0.2s",
              }}
            >
              {tab.label}
            </Button>
          ))}
        </Box>
      </Box>

      <Box sx={{ pt: 6 }}>
        {activeTab === "ocr" && (
          <Box>
            <Typography sx={{ color: "#d1d5db", mb: 2 }}>
              The OCR text extracted from the image will be displayed here. This
              text can be edited and copied for further use.
            </Typography>
            {ocrResult && (
              <Box
                sx={{
                  mt: 4,
                  p: 4,
                  backgroundColor: "#2a1f35",
                  borderRadius: "0.5rem",
                }}
              >
                <Typography sx={{ color: "white", whiteSpace: "pre-wrap" }}>
                  {ocrResult.text}
                </Typography>
              </Box>
            )}
          </Box>
        )}

        {activeTab === "grammar" && (
          <Box>
            <Typography variant="h4" sx={{ mb: 3, color: "white" }}>
              Grammar Analysis
            </Typography>
            {analysisResult && (
              <Box
                sx={{ mt: 4, display: "flex", flexDirection: "column", gap: 4 }}
              >
                <Box
                  sx={{
                    p: 4,
                    backgroundColor: "#2a1f35",
                    borderRadius: "0.5rem",
                  }}
                >
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
                </Box>
                <Box
                  sx={{
                    p: 4,
                    backgroundColor: "#2a1f35",
                    borderRadius: "0.5rem",
                  }}
                >
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
                </Box>
                {analysisResult.grammar_focus.rules && (
                  <Box
                    sx={{
                      p: 4,
                      backgroundColor: "#2a1f35",
                      borderRadius: "0.5rem",
                    }}
                  >
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
                  </Box>
                )}
                <Box
                  sx={{
                    p: 4,
                    backgroundColor: "#2a1f35",
                    borderRadius: "0.5rem",
                  }}
                >
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
                </Box>
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
              <Typography variant="h4" sx={{ color: "white" }}>
                Vocabulary Analysis
              </Typography>
              {analysisResult && analysisResult.vocabulary.length > 0 && (
                <Box sx={{ display: "flex", gap: 2 }}>
                  <Button
                    onClick={handleCheckAll}
                    sx={{
                      px: 3,
                      py: 2,
                      backgroundColor: "#6b7280",
                      color: "white",
                      borderRadius: "0.5rem",
                      fontWeight: 600,
                      "&:hover": {
                        backgroundColor: "#4b5563",
                      },
                      transition: "all 0.2s",
                    }}
                  >
                    Check/Uncheck All
                  </Button>
                  <Button
                    onClick={handleCopyVocabulary}
                    sx={{
                      px: 4,
                      py: 2,
                      backgroundColor: "var(--primary-color)",
                      color: "white",
                      borderRadius: "0.5rem",
                      fontWeight: 700,
                      display: "flex",
                      alignItems: "center",
                      gap: 2,
                      "&:hover": {
                        backgroundColor: "var(--primary-color)",
                        opacity: 0.9,
                        transform: "scale(1.05)",
                        boxShadow:
                          "0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -2px rgba(0, 0, 0, 0.05)",
                      },
                      "&:active": {
                        transform: "scale(0.95)",
                      },
                      transition: "all 0.2s",
                    }}
                  >
                    <Copy size={16} />
                    Copy
                  </Button>
                </Box>
              )}
            </Box>
            {analysisResult && (
              <Box
                sx={{ mt: 4, display: "flex", flexDirection: "column", gap: 2 }}
              >
                {analysisResult.vocabulary.map((item, index) => (
                  <Box
                    key={index}
                    sx={{
                      p: 4,
                      backgroundColor: "#2a1f35",
                      borderRadius: "0.5rem",
                      display: "flex",
                      justifyContent: "space-between",
                      alignItems: "center",
                    }}
                  >
                    <Box sx={{ display: "flex", alignItems: "center", gap: 2 }}>
                      <Checkbox
                        checked={checkedItems[index] || false}
                        onChange={() => handleCheckboxChange(index)}
                        sx={{
                          color: "#9ca3af",
                          "&.Mui-checked": {
                            color: "var(--primary-color)",
                          },
                        }}
                      />
                      <Typography sx={{ color: "white", fontWeight: "bold" }}>
                        {item.swedish}
                      </Typography>
                    </Box>
                    <Typography sx={{ color: "#9ca3af" }}>
                      {item.english}
                    </Typography>
                  </Box>
                ))}
              </Box>
            )}
          </Box>
        )}

        {activeTab === "extra_info" && (
          <Box>
            <Typography variant="h4" sx={{ mb: 3, color: "white" }}>
              Extra info
            </Typography>
            {resourcesResult ? (
              <Box
                sx={{
                  mt: 4,
                  p: 4,
                  backgroundColor: "#2a1f35",
                  borderRadius: "0.5rem",
                }}
              >
                <Typography sx={{ color: "white", whiteSpace: "pre-wrap" }}>
                  {convertUrlsToLinks(resourcesResult)}
                </Typography>
              </Box>
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
        anchorOrigin={{ vertical: 'bottom', horizontal: 'center' }}
      >
        <Alert
          onClose={() => setSnackbar({ ...snackbar, open: false })}
          severity={snackbar.severity}
          sx={{ width: '100%' }}
        >
          {snackbar.message}
        </Alert>
      </Snackbar>
    </Box>
  );
};

export default ResultsDisplay;