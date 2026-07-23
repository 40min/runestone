import React, { useCallback, useEffect, useRef, useState } from "react";
import { Box, Typography } from "@mui/material";
import {
  ErrorAlert,
  SectionTitle,
  Snackbar,
  analyzerShellGradients,
  buildAnalyzerShellSx,
} from "./ui";
import useGrammar from "../hooks/useGrammar";
import GrammarContentPanel from "./grammar/GrammarContentPanel";
import GrammarSidebar from "./grammar/GrammarSidebar";
import GrammarStartPanel from "./grammar/GrammarStartPanel";

type SnackbarState = {
  open: boolean;
  message: string;
  severity: "success" | "error" | "warning" | "info";
};

function getCheatsheetFromUrl(): string | null {
  if (typeof window === "undefined") return null;
  const params = new URLSearchParams(window.location.search);
  const cheatsheet = params.get("cheatsheet");
  return cheatsheet ? cheatsheet : null;
}

function filepathFromParam(value: string): string {
  return value.endsWith(".md") ? value : `${value}.md`;
}

function paramFromFilepath(filepath: string): string {
  return filepath.endsWith(".md") ? filepath.slice(0, -3) : filepath;
}

function setCheatsheetInUrl(filename: string | null, mode: "push" | "replace") {
  if (typeof window === "undefined") return;
  const url = new URL(window.location.href);
  url.searchParams.set("view", "grammar");
  if (filename) {
    url.searchParams.set("cheatsheet", paramFromFilepath(filename));
  } else {
    url.searchParams.delete("cheatsheet");
  }
  const fn = mode === "push" ? window.history.pushState : window.history.replaceState;
  fn.call(window.history, {}, "", url);
}

const GrammarView: React.FC = () => {
  const {
    cheatsheets,
    selectedCheatsheet,
    loading,
    error,
    fetchCheatsheetContent,
  } = useGrammar();
  const [selectedFilename, setSelectedFilename] = useState<string | null>(null);
  const [libraryQuery, setLibraryQuery] = useState("");
  const [expandedCategories, setExpandedCategories] = useState<Set<string>>(
    new Set()
  );
  const [snackbar, setSnackbar] = useState<SnackbarState>({ open: false, message: "", severity: "info" });
  const didInitFromUrlRef = useRef(false);
  const initialCheatsheetParamRef = useRef<string | null>(getCheatsheetFromUrl());

  const handleSelectionError = useCallback((err: unknown) => {
    console.error("Failed to load cheatsheet: ", err);
    setSnackbar({
      open: true,
      message: "Failed to load cheatsheet. Please try again.",
      severity: "error",
    });
  }, []);

  const syncSelectionFromUrl = useCallback(
    async (options?: { notifyOnInvalid?: boolean; cleanupInvalidUrl?: boolean }) => {
      const param = getCheatsheetFromUrl();
      if (!param) {
        setSelectedFilename(null);
        return;
      }

      const filepath = filepathFromParam(param);
      const hasCheatsheetList = cheatsheets.length > 0;
      const isValid = !hasCheatsheetList || cheatsheets.some((cs) => cs.filename === filepath);

      if (!isValid) {
        if (options?.cleanupInvalidUrl) {
          setCheatsheetInUrl(null, "replace");
        }
        setSelectedFilename(null);
        if (options?.notifyOnInvalid) {
          setSnackbar({
            open: true,
            message: "Unknown cheatsheet link.",
            severity: "error",
          });
        }
        return;
      }

      setSelectedFilename(filepath);
      await fetchCheatsheetContent(filepath);
    },
    [cheatsheets, fetchCheatsheetContent]
  );

  const handleCheatsheetClick = async (filename: string, options?: { pushUrl?: boolean }) => {
    setSelectedFilename(filename);
    if (options?.pushUrl !== false) {
      setCheatsheetInUrl(filename, "push");
    }
    await fetchCheatsheetContent(filename);
  };

  useEffect(() => {
    if (didInitFromUrlRef.current) return;

    const initial = initialCheatsheetParamRef.current;
    if (!initial) {
      didInitFromUrlRef.current = true;
      return;
    }

    if (cheatsheets.length === 0) return;

    didInitFromUrlRef.current = true;
    syncSelectionFromUrl({ notifyOnInvalid: true, cleanupInvalidUrl: true }).catch(handleSelectionError);
  }, [cheatsheets, handleSelectionError, syncSelectionFromUrl]);

  useEffect(() => {
    const handlePopState = () => {
      syncSelectionFromUrl({ notifyOnInvalid: false, cleanupInvalidUrl: true }).catch(handleSelectionError);
    };
    window.addEventListener("popstate", handlePopState);
    return () => {
      window.removeEventListener("popstate", handlePopState);
    };
  }, [handleSelectionError, syncSelectionFromUrl]);

  useEffect(() => {
    if (!selectedFilename || cheatsheets.length === 0) return;
    const match = cheatsheets.find((cs) => cs.filename === selectedFilename);
    if (!match || match.category === "General") return;
    setExpandedCategories((prev) => (prev.has(match.category) ? prev : new Set([...prev, match.category])));
  }, [cheatsheets, selectedFilename]);

  const toggleCategory = (category: string) => {
    setExpandedCategories((prev) => {
      const newSet = new Set(prev);
      if (newSet.has(category)) {
        newSet.delete(category);
      } else {
        newSet.add(category);
      }
      return newSet;
    });
  };

  const getShareLink = () => {
    if (typeof window === "undefined" || !selectedFilename) return null;
    const url = new URL(window.location.pathname, window.location.origin);
    url.searchParams.set("view", "grammar");
    url.searchParams.set("cheatsheet", paramFromFilepath(selectedFilename));
    return url.toString();
  };

  const handleCopyLink = async () => {
    const link = getShareLink();
    if (!link) return;

    try {
      await copyToClipboard(link);
      setSnackbar({ open: true, message: "Link copied to clipboard.", severity: "success" });
    } catch (err) {
      console.error("Failed to copy link: ", err);
      setSnackbar({ open: true, message: "Failed to copy link. Please try again.", severity: "error" });
    }
  };

  const copyToClipboard = async (text: string) => {
    if (!navigator.clipboard) {
      const textArea = document.createElement("textarea");
      textArea.value = text;
      document.body.appendChild(textArea);
      textArea.select();
      const successful = document.execCommand("copy");
      document.body.removeChild(textArea);
      if (!successful) throw new Error("Fallback copy failed");
      return;
    }
    await navigator.clipboard.writeText(text);
  };

  const handleCopyMarkdown = async () => {
    if (!selectedCheatsheet?.content) return;

    try {
      await copyToClipboard(selectedCheatsheet.content);
      setSnackbar({ open: true, message: "Markdown copied to clipboard.", severity: "success" });
    } catch (err) {
      console.error("Failed to copy markdown: ", err);
      setSnackbar({ open: true, message: "Failed to copy markdown. Please try again.", severity: "error" });
    }
  };

  const handleBackToStart = () => {
    setSelectedFilename(null);
    setCheatsheetInUrl(null, "push");
  };

  const selectedCheatsheetInfo = selectedFilename
    ? cheatsheets.find((cheatsheet) => cheatsheet.filename === selectedFilename)
    : null;

  return (
    <Box sx={{ py: { xs: 2, md: 4 } }}>
      <Box sx={{ mb: { xs: 4, md: 5 } }}>
        <SectionTitle
          variant="h2"
          marginBottom={1}
          sx={{
            color: "#f7f9ff",
            fontSize: { xs: "2.25rem", md: "3.25rem" },
            lineHeight: 1.05,
            letterSpacing: "-0.045em",
          }}
        >
          Grammar Cheatsheets
        </SectionTitle>
        <Typography
          sx={{
            maxWidth: 680,
            color: "#b8c5e3",
            fontSize: { xs: "1rem", md: "1.08rem" },
          }}
        >
          Quick Swedish grammar references for everyday study.
        </Typography>
      </Box>

      {error && (
        <Box sx={{ mb: 4 }}>
          <ErrorAlert message={error} />
        </Box>
      )}

      <Box
        sx={{
          display: "grid",
          gridTemplateColumns: { xs: "minmax(0, 1fr)", lg: "280px minmax(0, 1fr)" },
          alignItems: "start",
          gap: { xs: 4, lg: 5, xl: 7 },
        }}
      >
        <Box
          sx={{
            minWidth: 0,
            position: { lg: "sticky" },
            top: { lg: 116 },
            order: { xs: selectedFilename ? 2 : 1, lg: 1 },
          }}
        >
          <GrammarSidebar
            cheatsheets={cheatsheets}
            loading={loading}
            selectedFilename={selectedFilename}
            expandedCategories={expandedCategories}
            onBackToStart={handleBackToStart}
            onSelectCheatsheet={(filename) => {
              handleCheatsheetClick(filename).catch(handleSelectionError);
            }}
            onToggleCategory={toggleCategory}
            searchQuery={libraryQuery}
            onSearchQueryChange={setLibraryQuery}
          />
        </Box>

        <Box
          sx={{
            minWidth: 0,
            order: { xs: selectedFilename ? 1 : 2, lg: 2 },
          }}
        >
          {selectedFilename ? (
            <GrammarContentPanel
              category={selectedCheatsheetInfo?.category ?? null}
              title={
                selectedCheatsheetInfo?.title ?? paramFromFilepath(selectedFilename)
              }
              markdownContent={selectedCheatsheet?.content ?? null}
              loading={loading}
              hasError={Boolean(error)}
              onCopyMarkdown={() => {
                void handleCopyMarkdown();
              }}
              onCopyLink={() => {
                void handleCopyLink();
              }}
            />
          ) : (
            <Box
              sx={{
                minHeight: { xs: 360, lg: 620 },
                p: { xs: 2.5, sm: 4, lg: 5 },
                ...buildAnalyzerShellSx(analyzerShellGradients.emptyState),
              }}
            >
              <GrammarStartPanel />
            </Box>
          )}
        </Box>
      </Box>

      <Snackbar
        open={snackbar.open}
        message={snackbar.message}
        severity={snackbar.severity}
        onClose={() => setSnackbar((prev) => ({ ...prev, open: false }))}
        autoHideDuration={3000}
      />
    </Box>
  );
};

export default GrammarView;
