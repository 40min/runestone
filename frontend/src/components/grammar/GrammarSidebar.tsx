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
import { BookOpen, Layers3 } from "lucide-react";
import { LoadingSpinner } from "../ui";
import SearchInput from "../ui/SearchInput";
import type { CheatsheetInfo } from "./types";

const selectedCheatsheetSx = {
  minHeight: 42,
  borderRadius: "0.7rem",
  color: "#dbe5fb",
  transition: "background-color 160ms ease, color 160ms ease, transform 160ms ease",
  "&:hover": {
    backgroundColor: "rgba(148, 163, 184, 0.08)",
    color: "#ffffff",
    transform: "translateX(2px)",
  },
  "&.Mui-selected": {
    position: "relative",
    color: "#ffffff",
    background:
      "linear-gradient(90deg, rgba(56, 224, 123, 0.14), rgba(56, 224, 123, 0.08))",
    boxShadow: "0 10px 30px rgba(2, 8, 28, 0.2)",
    "&::before": {
      content: '""',
      position: "absolute",
      left: 0,
      top: 8,
      bottom: 8,
      width: 3,
      borderRadius: 999,
      backgroundColor: "var(--primary-color)",
    },
    "&:hover": {
      background:
        "linear-gradient(90deg, rgba(56, 224, 123, 0.18), rgba(56, 224, 123, 0.1))",
    },
  },
};

const cheatsheetTextSx = {
  "& .MuiListItemText-primary": {
    color: "inherit",
    fontSize: "0.92rem",
    fontWeight: 500,
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
  searchQuery: string;
  onSearchQueryChange: (value: string) => void;
};

function GrammarSidebar({
  cheatsheets,
  loading,
  selectedFilename,
  expandedCategories,
  onBackToStart,
  onSelectCheatsheet,
  onToggleCategory,
  searchQuery,
  onSearchQueryChange,
}: GrammarSidebarProps) {
  const {
    generalCheatsheets,
    categorizedCheatsheets,
    sortedCategoryKeys,
    visibleCheatsheetCount,
  } =
    React.useMemo(() => {
      const normalizedQuery = searchQuery.trim().toLocaleLowerCase();
      const visibleCheatsheets = normalizedQuery
        ? cheatsheets.filter(
            (cheatsheet) =>
              cheatsheet.title.toLocaleLowerCase().includes(normalizedQuery) ||
              cheatsheet.category.toLocaleLowerCase().includes(normalizedQuery)
          )
        : cheatsheets;
      const grouped = groupCheatsheets(visibleCheatsheets);
      return {
        ...grouped,
        sortedCategoryKeys: Object.keys(grouped.categorizedCheatsheets).sort(),
        visibleCheatsheetCount: visibleCheatsheets.length,
      };
    }, [cheatsheets, searchQuery]);

  return (
    <Box
      component="nav"
      aria-label="Grammar cheatsheet library"
      sx={{
        display: "flex",
        minWidth: 0,
        flexDirection: "column",
        color: "white",
      }}
    >
      <Box
        component="button"
        type="button"
        aria-label="Cheatsheet library"
        onClick={onBackToStart}
        sx={{
          display: "flex",
          alignItems: "center",
          gap: 1.5,
          width: "fit-content",
          mb: 2.5,
          color: "white",
          background: "none",
          border: 0,
          p: 0,
          font: "inherit",
          cursor: "pointer",
          textAlign: "left",
          "&:hover .library-title": {
            color: "var(--primary-color)",
          },
        }}
      >
        <BookOpen
          size={26}
          strokeWidth={1.8}
          aria-hidden="true"
          style={{ color: "var(--primary-color)" }}
        />
        <Typography
          className="library-title"
          variant="h6"
          sx={{
            fontSize: "1.05rem",
            fontWeight: 700,
            transition: "color 160ms ease",
          }}
        >
          Cheatsheet library
        </Typography>
      </Box>

      <SearchInput
        value={searchQuery}
        onChange={(event) => onSearchQueryChange(event.target.value)}
        onClear={() => onSearchQueryChange("")}
        placeholder="Search cheatsheets"
        ariaLabel="Search cheatsheet library"
        clearLabel="Clear cheatsheet library search"
        sx={{ mb: 2.5, maxWidth: "none" }}
        inputSx={{
          "& .MuiOutlinedInput-root": {
            minHeight: 44,
            backgroundColor: "rgba(7, 13, 43, 0.45)",
            borderRadius: "0.75rem",
            color: "#edf2ff",
            "& fieldset": {
              borderColor: "rgba(103, 124, 184, 0.42)",
            },
            "&:hover fieldset": {
              borderColor: "rgba(132, 153, 214, 0.62)",
            },
            "&.Mui-focused fieldset": {
              borderColor: "var(--primary-color)",
            },
          },
          "& .MuiInputBase-input": {
            py: 1.15,
            fontSize: "0.9rem",
            color: "#edf2ff",
            "&::placeholder": {
              color: "#91a2c9",
              opacity: 1,
            },
          },
        }}
      />

      {loading && cheatsheets.length === 0 ? (
        <LoadingSpinner />
      ) : cheatsheets.length > 0 &&
        generalCheatsheets.length === 0 &&
        sortedCategoryKeys.length === 0 ? (
        <Typography sx={{ px: 1, py: 2, color: "#8fa0c5", fontSize: "0.88rem" }}>
          No cheatsheets match “{searchQuery}”.
        </Typography>
      ) : (
        <List disablePadding sx={{ display: "grid", gap: 0.5 }}>
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
                <ListItemButton
                  onClick={() => onToggleCategory(category)}
                  aria-expanded={
                    expandedCategories.has(category) || Boolean(searchQuery.trim())
                  }
                  sx={{
                    minHeight: 44,
                    borderRadius: "0.7rem",
                    px: 1,
                    color: "#f3f6ff",
                    "&:hover": {
                      backgroundColor: "rgba(148, 163, 184, 0.06)",
                    },
                  }}
                >
                  <ListItemText
                    primary={category}
                    primaryTypographyProps={{
                      fontWeight: 700,
                      textTransform: "capitalize",
                      fontSize: "0.94rem",
                    }}
                    sx={cheatsheetTextSx}
                  />
                  {expandedCategories.has(category) || searchQuery.trim() ? (
                    <ExpandLess sx={{ color: "#9aabd0", fontSize: 20 }} />
                  ) : (
                    <ExpandMore sx={{ color: "#9aabd0", fontSize: 20 }} />
                  )}
                </ListItemButton>
              </ListItem>
              <Collapse
                in={expandedCategories.has(category) || Boolean(searchQuery.trim())}
              >
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

      <Box
        sx={{
          display: "flex",
          alignItems: "center",
          gap: 1,
          mt: 3,
          px: 1,
          color: "#8fa0c5",
        }}
      >
        <Layers3 size={16} aria-hidden="true" />
        <Typography sx={{ fontSize: "0.82rem" }}>
          {searchQuery.trim()
            ? `${visibleCheatsheetCount} matching ${
                visibleCheatsheetCount === 1 ? "cheatsheet" : "cheatsheets"
              }`
            : `${cheatsheets.length} ${
                cheatsheets.length === 1 ? "cheatsheet" : "cheatsheets"
              } available`}
        </Typography>
      </Box>
    </Box>
  );
}

export default GrammarSidebar;
