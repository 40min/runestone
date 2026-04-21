import React, { useCallback, useEffect, useRef, useState } from "react";
import { Box, Typography } from "@mui/material";
import { ContentCard, LoadingSpinner, ErrorAlert, SectionTitle, CustomButton, Snackbar } from "./ui";
import MarkdownDisplay from "./ui/MarkdownDisplay";
import useGrammar from "../hooks/useGrammar";
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
    searchResults = [],
    loading,
    error,
    searchLoading = false,
    searchError = null,
    fetchCheatsheetContent,
    searchGrammar = async () => undefined,
    clearSearch = () => undefined,
  } = useGrammar();
  const [selectedFilename, setSelectedFilename] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [hasSearched, setHasSearched] = useState(false);
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

  const handleSearch = async () => {
    const trimmedQuery = searchQuery.trim();
    if (!trimmedQuery) {
      setHasSearched(false);
      clearSearch();
      return;
    }

    setHasSearched(true);
    await searchGrammar(trimmedQuery);
  };

  const handleClearSearch = () => {
    setSearchQuery("");
    setHasSearched(false);
    clearSearch();
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

  return (
    <Box sx={{ py: 8 }}>
      <SectionTitle>Grammar Cheatsheets</SectionTitle>

      {error && (
        <Box sx={{ mb: 4 }}>
          <ErrorAlert message={error} />
        </Box>
      )}

      <Box sx={{ display: "flex", gap: 2, mt: 6 }}>
        {/* Left Pane: Cheatsheet List */}
        <Box sx={{ flexShrink: 0, width: "220px" }}>
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
          />
        </Box>

        {/* Right Pane: Content Display */}
        <Box sx={{ flex: 1 }}>
          <ContentCard>
            {selectedFilename ? (
              <>
                <Box sx={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 2, mb: 2 }}>
                  <Typography sx={{ color: "#9ca3af", fontSize: "0.875rem" }}>
                    {paramFromFilepath(selectedFilename)}
                  </Typography>
                  <Box sx={{ display: "flex", gap: 1 }}>
                    <CustomButton
                      variant="secondary"
                      size="small"
                      onClick={() => {
                        void handleCopyMarkdown();
                      }}
                    >
                      Copy markdown
                    </CustomButton>
                    <CustomButton
                      variant="secondary"
                      size="small"
                      onClick={() => {
                        void handleCopyLink();
                      }}
                    >
                      Copy link
                    </CustomButton>
                  </Box>
                </Box>
                {loading ? (
                  <LoadingSpinner />
                ) : selectedCheatsheet ? (
                  <MarkdownDisplay
                    markdownContent={selectedCheatsheet.content}
                  />
                ) : (
                  !error && (
                    <Typography sx={{ color: "#9ca3af" }}>
                      Failed to load cheatsheet content.
                    </Typography>
                  )
                )}
              </>
            ) : (
              <GrammarStartPanel
                searchQuery={searchQuery}
                searchResults={searchResults}
                searchLoading={searchLoading}
                searchError={searchError}
                hasSearched={hasSearched}
                onSearchQueryChange={setSearchQuery}
                onSearch={() => {
                  handleSearch().catch((err) => {
                    console.error("Failed to search grammar: ", err);
                  });
                }}
                onClearSearch={handleClearSearch}
                onSelectSearchResult={(filename) => {
                  handleCheatsheetClick(filename).catch(handleSelectionError);
                }}
              />
            )}
          </ContentCard>
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
