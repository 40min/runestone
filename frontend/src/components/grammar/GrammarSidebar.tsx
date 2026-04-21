import React from "react";
import {
  Box,
  Collapse,
  List,
  ListItem,
  ListItemButton,
  ListItemText,
  Typography,
} from "@mui/material";
import { ExpandLess, ExpandMore } from "@mui/icons-material";
import { ContentCard, LoadingSpinner } from "../ui";
import type { CheatsheetInfo } from "./types";

const selectedCheatsheetSx = {
  "&.Mui-selected": {
    backgroundColor: "rgba(147, 51, 234, 0.1)",
    "&:hover": {
      backgroundColor: "rgba(147, 51, 234, 0.2)",
    },
  },
};

const cheatsheetTextSx = {
  "& .MuiListItemText-primary": {
    color: "white",
  },
};

function groupCheatsheets(cheatsheets: CheatsheetInfo[]) {
  return cheatsheets.reduce<{
    generalCheatsheets: CheatsheetInfo[];
    categorizedCheatsheets: Record<string, CheatsheetInfo[]>;
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
}

type CheatsheetListItemProps = {
  cheatsheet: CheatsheetInfo;
  selectedFilename: string | null;
  onSelect: (filename: string) => void;
  nested?: boolean;
};

function CheatsheetListItem({
  cheatsheet,
  selectedFilename,
  onSelect,
  nested = false,
}: CheatsheetListItemProps) {
  return (
    <ListItem disablePadding>
      <ListItemButton
        onClick={() => onSelect(cheatsheet.filename)}
        selected={selectedFilename === cheatsheet.filename}
        sx={nested ? { pl: 4, ...selectedCheatsheetSx } : selectedCheatsheetSx}
      >
        <ListItemText primary={cheatsheet.title} sx={cheatsheetTextSx} />
      </ListItemButton>
    </ListItem>
  );
}

type GrammarSidebarProps = {
  cheatsheets: CheatsheetInfo[];
  loading: boolean;
  selectedFilename: string | null;
  expandedCategories: Set<string>;
  onBackToStart: () => void;
  onSelectCheatsheet: (filename: string) => void;
  onToggleCategory: (category: string) => void;
};

function GrammarSidebar({
  cheatsheets,
  loading,
  selectedFilename,
  expandedCategories,
  onBackToStart,
  onSelectCheatsheet,
  onToggleCategory,
}: GrammarSidebarProps) {
  const { generalCheatsheets, categorizedCheatsheets, sortedCategoryKeys } =
    React.useMemo(() => {
      const grouped = groupCheatsheets(cheatsheets);
      return {
        ...grouped,
        sortedCategoryKeys: Object.keys(grouped.categorizedCheatsheets).sort(),
      };
    }, [cheatsheets]);

  return (
    <ContentCard>
      <Typography
        variant="h6"
        sx={{ color: "var(--primary-color)", mb: 2 }}
      >
        <Box
          component="button"
          type="button"
          onClick={onBackToStart}
          sx={{
            color: "inherit",
            background: "none",
            border: "none",
            p: 0,
            m: 0,
            font: "inherit",
            cursor: "pointer",
            textAlign: "left",
          }}
        >
          Available Cheatsheets
        </Box>
      </Typography>
      {loading && cheatsheets.length === 0 ? (
        <LoadingSpinner />
      ) : (
        <List>
          {generalCheatsheets.map((cheatsheet) => (
            <CheatsheetListItem
              key={cheatsheet.filename}
              cheatsheet={cheatsheet}
              selectedFilename={selectedFilename}
              onSelect={onSelectCheatsheet}
            />
          ))}

          {sortedCategoryKeys.map((category) => (
            <React.Fragment key={category}>
              <ListItem disablePadding>
                <ListItemButton onClick={() => onToggleCategory(category)}>
                  <ListItemText
                    primary={category}
                    primaryTypographyProps={{ fontWeight: "bold" }}
                    sx={cheatsheetTextSx}
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
                  {categorizedCheatsheets[category].map((cheatsheet) => (
                    <CheatsheetListItem
                      key={cheatsheet.filename}
                      cheatsheet={cheatsheet}
                      selectedFilename={selectedFilename}
                      onSelect={onSelectCheatsheet}
                      nested
                    />
                  ))}
                </List>
              </Collapse>
            </React.Fragment>
          ))}
        </List>
      )}
    </ContentCard>
  );
}

export default GrammarSidebar;
