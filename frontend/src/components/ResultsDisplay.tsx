import React, { useState, useEffect, useMemo } from "react";
import {
  Box,
  Typography,
  Snackbar,
  Alert,
  IconButton,
  CircularProgress,
} from "@mui/material";
import type { AlertColor } from "@mui/material";
import DOMPurify from "dompurify";
import { ArrowRight, Copy, Save, Sparkles } from "lucide-react";
import { v4 as uuidv4 } from "uuid";
import {
  CustomButton,
  ErrorAlert,
  SurfaceCard,
  TabNavigation,
  StyledCheckbox,
  DataTable,
  analyzerShellGradients,
  analyzerSurfaceCardSx,
  buildAnalyzerShellSx,
} from "./ui";
import { parseMarkdown } from "../utils/markdownParser";
import type {
  OCRResult,
  VocabularyItem,
  EnrichedVocabularyItem,
  ContentAnalysis,
  ProcessingStep,
} from "../hooks/useImageProcessing";

const enrichVocabularyItems = (
  vocabulary: VocabularyItem[]
): EnrichedVocabularyItem[] => {
  return vocabulary.map((item) => ({
    ...item,
    id: item.id || uuidv4(),
  }));
};

interface ResultsDisplayProps {
  ocrResult: OCRResult | null;
  analysisResult: ContentAnalysis | null;
  error: string | null;
  saveVocabulary: (
    vocabulary: EnrichedVocabularyItem[],
    enrich: boolean
  ) => Promise<void>;
  onVocabularyUpdated?: (updatedVocabulary: EnrichedVocabularyItem[]) => void;
  processingStep: ProcessingStep;
  isProcessing: boolean;
  onAnalyzeOcrText?: () => Promise<void> | void;
  showAnalyzeOcrAction?: boolean;
  isAnalyzeOcrDisabled?: boolean;
  analyzeOcrButtonIcon?: React.ReactNode;
}

const ResultsDisplay: React.FC<ResultsDisplayProps> = ({
  ocrResult,
  analysisResult,
  error,
  saveVocabulary,
  onVocabularyUpdated,
  processingStep,
  isProcessing,
  onAnalyzeOcrText,
  showAnalyzeOcrAction = false,
  isAnalyzeOcrDisabled = false,
  analyzeOcrButtonIcon,
}) => {
  const availableTabs = useMemo(
    () =>
      [ocrResult && "ocr", analysisResult && "grammar", analysisResult && "vocabulary"].filter(
        Boolean
      ) as string[],
    [ocrResult, analysisResult]
  );
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
  const [hideKnown, setHideKnown] = useState(false);
  const [copyButtonText, setCopyButtonText] = useState("Copy");
  const [enrichedVocabulary, setEnrichedVocabulary] = useState<
    EnrichedVocabularyItem[]
  >([]);

  useEffect(() => {
    if (availableTabs.length > 0) {
      setActiveTab((currentTab) =>
        availableTabs.includes(currentTab) ? currentTab : availableTabs[0]
      );
    }
  }, [availableTabs]);

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

  const filteredVocabulary = useMemo(
    () => enrichedVocabulary.filter((item) => !hideKnown || !item.known),
    [enrichedVocabulary, hideKnown]
  );
  const renderedOcrHtml = useMemo(
    () => parseMarkdown(ocrResult?.text ?? ""),
    [ocrResult?.text]
  );

  if (!ocrResult && !analysisResult && !isProcessing) {
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
      if (!navigator.clipboard) {
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

      const updatedVocabulary = enrichedVocabulary.map((item) =>
        checkedItems.get(item.id) ? { ...item, known: true } : item
      );
      setEnrichedVocabulary(updatedVocabulary);
      setCheckedItems(new Map());

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
      if (!navigator.clipboard) {
        const textArea = document.createElement("textarea");
        textArea.value = ocrResult.text;
        document.body.appendChild(textArea);
        textArea.select();
        document.execCommand("copy");
        document.body.removeChild(textArea);
        setCopyButtonText("Copied!");
        setSnackbar({
          open: true,
          message: "Recognized text copied to clipboard!",
          severity: "success",
        });
        setTimeout(() => setCopyButtonText("Copy"), 2000);
        return;
      }

      await navigator.clipboard.writeText(ocrResult.text);
      setCopyButtonText("Copied!");
      setSnackbar({
        open: true,
        message: "Recognized text copied to clipboard!",
        severity: "success",
      });
      setTimeout(() => setCopyButtonText("Copy"), 2000);
    } catch (err) {
      console.error("Failed to copy OCR text: ", err);
      setSnackbar({
        open: true,
        message: "Failed to copy recognized text. Please try again.",
        severity: "error",
      });
    }
  };

  const tabs = [
    ocrResult && { id: "ocr", label: "OCR Text" },
    analysisResult && { id: "grammar", label: "Grammar" },
    analysisResult && { id: "vocabulary", label: "Vocabulary" },
  ].filter(Boolean) as { id: string; label: string }[];

  const processingHeadline =
    processingStep === "ANALYZING"
      ? "Building grammar and vocabulary insights"
      : "Reading the textbook page";
  const processingBody =
    processingStep === "ANALYZING"
      ? "The OCR text is ready. We are extracting the key grammar focus and vocabulary now."
      : "We are extracting the text from your image and preparing the analysis workspace.";
  const showInlineProcessingNotice =
    isProcessing &&
    processingStep === "ANALYZING" &&
    Boolean(ocrResult) &&
    !analysisResult &&
    !error;

  if (isProcessing && !ocrResult && !analysisResult && !error) {
    return (
      <Box
        sx={{
          minHeight: { xs: 320, lg: 420 },
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          px: { xs: 3, md: 5 },
          textAlign: "center",
          ...buildAnalyzerShellSx(analyzerShellGradients.processing),
        }}
      >
        <Box sx={{ maxWidth: 520 }}>
          <Box
            sx={{
              mx: "auto",
              mb: 2.5,
              width: 76,
              height: 76,
              borderRadius: "999px",
              border: "1px solid rgba(129, 149, 218, 0.38)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              background: "rgba(14, 21, 64, 0.7)",
              boxShadow: "0 0 0 10px rgba(50, 69, 145, 0.12)",
            }}
          >
            <CircularProgress size={32} sx={{ color: "var(--primary-color)" }} />
          </Box>
          <Typography
            sx={{
              color: "#f4f7ff",
              fontWeight: 800,
              fontSize: { xs: "1.6rem", md: "2rem" },
              lineHeight: 1.15,
              mb: 1.25,
            }}
          >
            {processingHeadline}
          </Typography>
          <Typography
            sx={{
              color: "#bcc8e7",
              fontSize: { xs: "1rem", md: "1.1rem" },
              lineHeight: 1.75,
            }}
          >
            {processingBody}
          </Typography>
        </Box>
      </Box>
    );
  }

  return (
    <Box
      sx={{
        overflow: "hidden",
        ...buildAnalyzerShellSx(analyzerShellGradients.results),
      }}
    >
      {error && (
        <Box sx={{ p: { xs: 1.5, md: 2 } }}>
          <ErrorAlert message={error} />
        </Box>
      )}

      {tabs.length > 0 && (
        <TabNavigation
          tabs={tabs}
          activeTab={activeTab}
          onTabChange={setActiveTab}
          containerSx={{
            px: { xs: 1.5, md: 2.5 },
            borderColor: "rgba(106, 120, 178, 0.4)",
          }}
          tabsSx={{ gap: { xs: 0.75, md: 3.5 } }}
          buttonSx={{
            px: { xs: 1.2, md: 2.25 },
            py: 1.25,
            fontSize: { xs: "0.98rem", md: "1.05rem" },
          }}
        />
      )}

      <Box sx={{ px: { xs: 1.5, md: 2.5 }, pt: 2.5, pb: 2.5 }}>
        {showInlineProcessingNotice && (
          <Box
            sx={{
              display: "flex",
              alignItems: { xs: "flex-start", sm: "center" },
              gap: 1.25,
              mb: 2.5,
              px: 1.5,
              py: 1.25,
              borderRadius: "0.9rem",
              border: "1px solid rgba(93, 210, 137, 0.22)",
              background: "rgba(25, 38, 88, 0.56)",
              boxShadow: "inset 0 1px 0 rgba(255,255,255,0.03)",
            }}
          >
            <CircularProgress
              size={20}
              sx={{ color: "var(--primary-color)", flexShrink: 0, mt: { xs: 0.2, sm: 0 } }}
            />
            <Box>
              <Typography
                sx={{ color: "#edf4ff", fontWeight: 700, lineHeight: 1.25 }}
              >
                {processingHeadline}
              </Typography>
              <Typography
                sx={{ color: "#9fb0d9", fontSize: "0.94rem", mt: 0.35 }}
              >
                OCR is ready. We are turning it into the final analysis now.
              </Typography>
            </Box>
          </Box>
        )}

        {activeTab === "ocr" && ocrResult && (
          <Box>
            <Box
              sx={{
                display: "flex",
                justifyContent: "space-between",
                alignItems: { xs: "stretch", sm: "center" },
                gap: 1.5,
                flexDirection: { xs: "column", sm: "row" },
                mb: 2,
              }}
            >
              <Box>
                <Typography
                  sx={{
                    color: "#f0f4ff",
                    fontWeight: 700,
                    fontSize: { xs: "1.15rem", md: "1.25rem" },
                  }}
                >
                  Recognized text
                </Typography>
                <Typography
                  sx={{ color: "#92a5d6", fontSize: "0.92rem", mt: 0.5 }}
                >
                  Review the OCR output or continue into grammar and vocabulary
                  analysis.
                </Typography>
              </Box>
              <Box
                sx={{
                  display: "flex",
                  alignItems: "center",
                  justifyContent: { xs: "space-between", sm: "flex-end" },
                  gap: 1,
                  width: { xs: "100%", sm: "auto" },
                }}
              >
                {showAnalyzeOcrAction && (
                  <CustomButton
                    onClick={() => onAnalyzeOcrText?.()}
                    disabled={isAnalyzeOcrDisabled}
                    startIcon={analyzeOcrButtonIcon ?? <Sparkles size={16} />}
                    endIcon={<ArrowRight size={16} />}
                    sx={{
                      minHeight: "3rem",
                      borderRadius: "0.85rem",
                      px: 2.25,
                      fontWeight: 700,
                    }}
                  >
                    Analyze OCR Text
                  </CustomButton>
                )}
                <IconButton
                  onClick={handleCopyOCRText}
                  sx={{
                    color: "var(--primary-color)",
                    border: "1px solid rgba(93, 210, 137, 0.32)",
                    borderRadius: "0.8rem",
                    "&:hover": {
                      backgroundColor: "rgba(61, 221, 136, 0.08)",
                    },
                  }}
                  title={copyButtonText}
                >
                  <Copy size={20} />
                </IconButton>
              </Box>
            </Box>
            <SurfaceCard sx={{ minHeight: 240 }}>
              <Box
                sx={{ color: "white" }}
                className="markdown-content"
                dangerouslySetInnerHTML={{
                  __html: DOMPurify.sanitize(renderedOcrHtml),
                }}
              />
            </SurfaceCard>
          </Box>
        )}

        {activeTab === "grammar" && analysisResult && (
          <Box>
            <Box sx={{ mb: 2.5 }}>
              <Typography
                sx={{
                  color: "#f0f4ff",
                  fontWeight: 800,
                  fontSize: { xs: "1.35rem", md: "1.6rem" },
                }}
              >
                Grammar focus
              </Typography>
              <Typography sx={{ color: "#94a7d7", mt: 0.5 }}>
                Key concept, explanation, and support notes from the analyzed
                page.
              </Typography>
            </Box>

            <Box sx={{ display: "flex", flexDirection: "column", gap: 2 }}>
              <SurfaceCard>
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
              </SurfaceCard>

              <SurfaceCard>
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
              </SurfaceCard>

              {analysisResult.grammar_focus.rules && (
                <SurfaceCard>
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
                </SurfaceCard>
              )}

              <SurfaceCard>
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
              </SurfaceCard>
            </Box>
          </Box>
        )}

        {activeTab === "vocabulary" && (
          <Box>
            <Box
              sx={{
                display: "flex",
                justifyContent: "space-between",
                alignItems: "flex-start",
                gap: 2,
                flexDirection: { xs: "column", md: "row" },
                mb: 2.5,
              }}
            >
              <Box>
                <Typography
                  sx={{
                    color: "#f0f4ff",
                    fontWeight: 800,
                    fontSize: { xs: "1.4rem", md: "1.75rem" },
                  }}
                >
                  Vocabulary
                </Typography>
                <Typography sx={{ color: "#94a7d7", mt: 0.5 }}>
                  Select words to copy or save, then refine the list with the
                  filters on the right.
                </Typography>
              </Box>

              {analysisResult && enrichedVocabulary.length > 0 && (
                <Box
                  sx={{
                    display: "flex",
                    flexDirection: "column",
                    alignItems: { xs: "stretch", lg: "flex-end" },
                    gap: 1.4,
                    width: { xs: "100%", md: "auto" },
                  }}
                >
                  <Box
                    sx={{
                      display: "flex",
                      gap: 1.2,
                      flexWrap: "wrap",
                      width: { xs: "100%", lg: "auto" },
                    }}
                  >
                    <CustomButton
                      variant="primary"
                      onClick={handleSaveVocabulary}
                      startIcon={<Save size={16} />}
                      sx={{
                        minWidth: { xs: "100%", sm: 0 },
                        minHeight: "3rem",
                        borderRadius: "0.85rem",
                        px: 2.4,
                        fontWeight: 700,
                      }}
                    >
                      Save to Database
                    </CustomButton>
                    <CustomButton
                      variant="primary"
                      onClick={handleCopyVocabulary}
                      startIcon={<Copy size={16} />}
                      sx={{
                        minWidth: { xs: "100%", sm: 0 },
                        minHeight: "3rem",
                        borderRadius: "0.85rem",
                        px: 2.4,
                        fontWeight: 700,
                      }}
                    >
                      Copy
                    </CustomButton>
                  </Box>

                  <Box
                    sx={{
                      display: "flex",
                      alignItems: { xs: "stretch", lg: "center" },
                      justifyContent: { xs: "space-between", lg: "flex-end" },
                      flexDirection: { xs: "column", sm: "row" },
                      gap: 1.5,
                      borderLeft: {
                        xs: "none",
                        lg: "1px solid rgba(106, 120, 178, 0.28)",
                      },
                      pl: { xs: 0, lg: 2 },
                    }}
                  >
                    <Box sx={{ display: "flex", alignItems: "flex-start", gap: 1 }}>
                      <StyledCheckbox
                        id="enrich-grammar-checkbox"
                        checked={enrichVocabulary}
                        onChange={(checked) => setEnrichVocabulary(checked)}
                      />
                      <Typography sx={{ color: "white", lineHeight: 1.4 }}>
                        Enrich with grammar info
                      </Typography>
                    </Box>
                    <Box sx={{ display: "flex", alignItems: "flex-start", gap: 1 }}>
                      <StyledCheckbox
                        id="hide-known-words-checkbox"
                        checked={hideKnown}
                        onChange={(checked) => setHideKnown(checked)}
                      />
                      <Typography sx={{ color: "white", lineHeight: 1.4 }}>
                        Hide known words
                      </Typography>
                    </Box>
                  </Box>
                </Box>
              )}
            </Box>

            {analysisResult && (
              <Box sx={{ mt: 3 }}>
                <DataTable
                  selectable={true}
                  selectedItems={checkedItems}
                  onSelectionChange={handleCheckboxChange}
                  onSelectAll={handleCheckAll}
                  masterCheckboxId="vocabulary-master-checkbox"
                  rowCheckboxIdPrefix="vocabulary-item"
                  sx={{
                    ...analyzerSurfaceCardSx,
                  }}
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
                  renderMobileRow={(row, _index, checkbox) => (
                    <Box
                      key={row.id}
                      sx={{
                        ...analyzerSurfaceCardSx,
                        p: 1.35,
                        display: "flex",
                        alignItems: "center",
                        gap: 1.5,
                      }}
                    >
                      {checkbox}
                      <Box sx={{ minWidth: 0, flex: "0 0 30%" }}>
                        <Typography
                          sx={{
                            color: "#f4f7ff",
                            fontWeight: 700,
                            lineHeight: 1.25,
                            fontSize: "1.05rem",
                            wordBreak: "break-word",
                          }}
                        >
                          {String(row.swedish || "—")}
                        </Typography>
                        <Typography
                          sx={{
                            color: "#adbce4",
                            fontSize: "0.95rem",
                            lineHeight: 1.2,
                            mt: 0.25,
                          }}
                        >
                          {String(row.english || "—")}
                        </Typography>
                      </Box>
                      <Typography
                        sx={{
                          color: "#d0d9ef",
                          flex: 1,
                          fontSize: "1rem",
                          lineHeight: 1.3,
                          whiteSpace: "normal",
                          wordBreak: "break-word",
                        }}
                      >
                        {String(row.example_phrase || "—")}
                      </Typography>
                    </Box>
                  )}
                />
              </Box>
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
