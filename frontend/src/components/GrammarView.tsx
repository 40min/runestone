import React, { useState } from "react";
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
import { ContentCard, LoadingSpinner, ErrorAlert, SectionTitle } from "./ui";
import MarkdownDisplay from "./ui/MarkdownDisplay";
import useGrammar from "../hooks/useGrammar";

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

  const handleCheatsheetClick = async (filename: string) => {
    setSelectedFilename(filename);
    await fetchCheatsheetContent(filename);
  };

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

  return (
    <Box sx={{ py: 8 }}>
      <SectionTitle>Grammar Cheatsheets</SectionTitle>

      {error && (
        <Box sx={{ mb: 4 }}>
          <ErrorAlert message={error} />
        </Box>
      )}

      <Box sx={{ display: "flex", gap: 4, mt: 6 }}>
        {/* Left Pane: Cheatsheet List */}
        <Box sx={{ flex: 1, maxWidth: "300px" }}>
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
        <Box sx={{ flex: 2 }}>
          <ContentCard>
            {selectedFilename ? (
              <>
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
    </Box>
  );
};

export default GrammarView;
