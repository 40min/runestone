import React, { useState } from "react";
import {
  Box,
  Typography,
  List,
  ListItem,
  ListItemButton,
  ListItemText,
} from "@mui/material";
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

  const handleCheatsheetClick = async (filename: string) => {
    setSelectedFilename(filename);
    await fetchCheatsheetContent(filename);
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
                {cheatsheets.map((cheatsheet) => (
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
