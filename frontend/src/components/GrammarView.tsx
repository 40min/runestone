import React, { useEffect, useRef, useState } from "react";
import {
  Box,
  Typography,
  List,
  ListItem,
  ListItemButton,
  ListItemText,
  Collapse,
} from "@mui/material";
import { ExpandMore, ExpandLess } from "@mui/icons-material";
import { ContentCard, LoadingSpinner, ErrorAlert, SectionTitle, CustomButton, Snackbar } from "./ui";
import MarkdownDisplay from "./ui/MarkdownDisplay";
import useGrammar from "../hooks/useGrammar";

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
  const [expandedCategories, setExpandedCategories] = useState<Set<string>>(
    new Set()
  );
  const [snackbar, setSnackbar] = useState<{
    open: boolean;
    message: string;
    severity: "success" | "error" | "warning" | "info";
  }>({ open: false, message: "", severity: "info" });
  const didInitFromUrlRef = useRef(false);

  const handleCheatsheetClick = async (filename: string, options?: { pushUrl?: boolean }) => {
    setSelectedFilename(filename);
    if (options?.pushUrl !== false) {
      setCheatsheetInUrl(filename, "push");
    }
    await fetchCheatsheetContent(filename);
  };

  useEffect(() => {
    if (didInitFromUrlRef.current) return;
    didInitFromUrlRef.current = true;

    const initial = getCheatsheetFromUrl();
    if (!initial) return;

    const filepath = filepathFromParam(initial);
    setSelectedFilename(filepath);
    setCheatsheetInUrl(filepath, "replace");
    void fetchCheatsheetContent(filepath);
  }, [fetchCheatsheetContent]);

  useEffect(() => {
    if (!selectedFilename || cheatsheets.length === 0) return;
    const match = cheatsheets.find((cs) => cs.filename === selectedFilename);
    if (!match || match.category === "General") return;
    setExpandedCategories((prev) => (prev.has(match.category) ? prev : new Set([...prev, match.category])));
  }, [cheatsheets, selectedFilename]);

  // Group cheatsheets by category
  const { generalCheatsheets, categorizedCheatsheets } = cheatsheets.reduce<{
    generalCheatsheets: typeof cheatsheets;
    categorizedCheatsheets: Record<string, typeof cheatsheets>;
  }>(
    (acc, cheatsheet) => {
      if (cheatsheet.category === "General") {
        acc.generalCheatsheets.push(cheatsheet);
      } else {
        if (!acc.categorizedCheatsheets[cheatsheet.category]) {
          acc.categorizedCheatsheets[cheatsheet.category] = [];
        }
        acc.categorizedCheatsheets[cheatsheet.category].push(cheatsheet);
      }
      return acc;
    },
    { generalCheatsheets: [], categorizedCheatsheets: {} }
  );

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
    const url = new URL(window.location.href);
    url.searchParams.set("view", "grammar");
    url.searchParams.set("cheatsheet", paramFromFilepath(selectedFilename));
    return url.toString();
  };

  const handleCopyLink = async () => {
    const link = getShareLink();
    if (!link) return;

    try {
      if (!navigator.clipboard) {
        const textArea = document.createElement("textarea");
        textArea.value = link;
        document.body.appendChild(textArea);
        textArea.select();
        const successful = document.execCommand("copy");
        document.body.removeChild(textArea);
        if (!successful) throw new Error("Fallback copy failed");
      } else {
        await navigator.clipboard.writeText(link);
      }
      setSnackbar({ open: true, message: "Link copied to clipboard.", severity: "success" });
    } catch (err) {
      console.error("Failed to copy link: ", err);
      setSnackbar({ open: true, message: "Failed to copy link. Please try again.", severity: "error" });
    }
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
          <ContentCard>
            <Typography
              variant="h6"
              sx={{ color: "var(--primary-color)", mb: 2 }}
            >
              Available Cheatsheets
            </Typography>
            {loading && cheatsheets.length === 0 ? (
              <LoadingSpinner />
            ) : (
              <List>
                {/* Render General cheatsheets at root level */}
                {generalCheatsheets.map((cheatsheet) => (
                  <ListItem key={cheatsheet.filename} disablePadding>
                    <ListItemButton
                      onClick={() => handleCheatsheetClick(cheatsheet.filename)}
                      selected={selectedFilename === cheatsheet.filename}
                      sx={{
                        "&.Mui-selected": {
                          backgroundColor: "rgba(147, 51, 234, 0.1)",
                          "&:hover": {
                            backgroundColor: "rgba(147, 51, 234, 0.2)",
                          },
                        },
                      }}
                    >
                      <ListItemText
                        primary={cheatsheet.title}
                        sx={{
                          "& .MuiListItemText-primary": {
                            color: "white",
                          },
                        }}
                      />
                    </ListItemButton>
                  </ListItem>
                ))}

                {/* Render categorized cheatsheets with collapsible categories */}
                {Object.keys(categorizedCheatsheets)
                  .sort()
                  .map((category) => (
                    <React.Fragment key={category}>
                      <ListItem disablePadding>
                        <ListItemButton
                          onClick={() => toggleCategory(category)}
                        >
                          <ListItemText
                            primary={category}
                            primaryTypographyProps={{ fontWeight: "bold" }}
                            sx={{
                              "& .MuiListItemText-primary": {
                                color: "white",
                              },
                            }}
                          />
                          {expandedCategories.has(category) ? (
                            <ExpandLess />
                          ) : (
                            <ExpandMore />
                          )}
                        </ListItemButton>
                      </ListItem>
                      <Collapse in={expandedCategories.has(category)}>
                        <List component="div" disablePadding>
                          {categorizedCheatsheets[category].map(
                            (cheatsheet) => (
                              <ListItem
                                key={cheatsheet.filename}
                                disablePadding
                              >
                                <ListItemButton
                                  onClick={() =>
                                    handleCheatsheetClick(cheatsheet.filename)
                                  }
                                  selected={
                                    selectedFilename === cheatsheet.filename
                                  }
                                  sx={{
                                    pl: 4,
                                    "&.Mui-selected": {
                                      backgroundColor:
                                        "rgba(147, 51, 234, 0.1)",
                                      "&:hover": {
                                        backgroundColor:
                                          "rgba(147, 51, 234, 0.2)",
                                      },
                                    },
                                  }}
                                >
                                  <ListItemText
                                    primary={cheatsheet.title}
                                    sx={{
                                      "& .MuiListItemText-primary": {
                                        color: "white",
                                      },
                                    }}
                                  />
                                </ListItemButton>
                              </ListItem>
                            )
                          )}
                        </List>
                      </Collapse>
                    </React.Fragment>
                  ))}
              </List>
            )}
          </ContentCard>
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
              <Typography sx={{ color: "#9ca3af" }}>
                Select a cheatsheet from the list to view its content.
              </Typography>
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
