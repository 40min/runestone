import {
  Box,
  List,
  ListItem,
  ListItemButton,
  ListItemText,
  Typography,
} from "@mui/material";
import type { GrammarSearchResult } from "../../hooks/useGrammar";
import { ErrorAlert, LoadingSpinner, SearchInput } from "../ui";

type GrammarStartPanelProps = {
  searchQuery: string;
  searchResults: GrammarSearchResult[];
  searchLoading: boolean;
  searchError: string | null;
  hasSearched: boolean;
  onSearchQueryChange: (value: string) => void;
  onSearch: () => void;
  onClearSearch: () => void;
  onSelectSearchResult: (filename: string) => void;
};

function GrammarStartPanel({
  searchQuery,
  searchResults,
  searchLoading,
  searchError,
  hasSearched,
  onSearchQueryChange,
  onSearch,
  onClearSearch,
  onSelectSearchResult,
}: GrammarStartPanelProps) {
  return (
    <Box sx={{ maxWidth: 720 }}>
      <Typography
        variant="h4"
        sx={{
          color: "#f7f9ff",
          mb: 1.25,
          fontSize: { xs: "1.65rem", sm: "2rem" },
          fontWeight: 700,
          letterSpacing: "-0.025em",
        }}
      >
        Search grammar cheatsheets
      </Typography>
      <Typography sx={{ maxWidth: 560, color: "#aab8d7", lineHeight: 1.7 }}>
        Search for a grammar topic, or select a cheatsheet from the list.
      </Typography>

      <SearchInput
        value={searchQuery}
        onChange={(event) => onSearchQueryChange(event.target.value)}
        onSearch={onSearch}
        onClear={onClearSearch}
        placeholder="Search grammar topics..."
        ariaLabel="Search grammar topics"
        clearLabel="Clear grammar topic search"
        sx={{ mt: 4, mb: 4, maxWidth: 600 }}
        inputSx={{
          "& .MuiOutlinedInput-root": {
            minHeight: 50,
            backgroundColor: "rgba(7, 13, 43, 0.5)",
            borderRadius: "0.8rem",
            color: "#edf2ff",
            "& fieldset": {
              borderColor: "rgba(103, 124, 184, 0.46)",
            },
            "&:hover fieldset": {
              borderColor: "rgba(132, 153, 214, 0.66)",
            },
            "&.Mui-focused fieldset": {
              borderColor: "var(--primary-color)",
            },
          },
          "& .MuiInputBase-input": {
            color: "#edf2ff",
            "&::placeholder": {
              color: "#91a2c9",
              opacity: 1,
            },
          },
        }}
      />

      {searchError && (
        <Box sx={{ mb: 3 }}>
          <ErrorAlert message={searchError} />
        </Box>
      )}

      {searchLoading ? (
        <LoadingSpinner />
      ) : hasSearched && searchResults.length === 0 && !searchError ? (
        <Typography sx={{ color: "#9ca3af" }}>
          No matching grammar pages found.
        </Typography>
      ) : searchResults.length > 0 ? (
        <List
          disablePadding
          aria-label="Grammar search results"
          sx={{ display: "grid", gap: 1.25 }}
        >
          {searchResults.map((result) => (
            <ListItem key={result.path || result.url} disablePadding>
              <ListItemButton
                onClick={() => onSelectSearchResult(result.path)}
                sx={{
                  border: "1px solid rgba(103, 124, 184, 0.38)",
                  borderRadius: "0.75rem",
                  backgroundColor: "rgba(15, 25, 61, 0.58)",
                  transition: "all 160ms ease",
                  "&:hover": {
                    borderColor: "rgba(56, 224, 123, 0.44)",
                    backgroundColor: "rgba(22, 38, 77, 0.72)",
                    transform: "translateY(-1px)",
                  },
                }}
              >
                <ListItemText
                  primary={result.title || result.path}
                  secondary={result.path}
                  sx={{
                    "& .MuiListItemText-primary": {
                      color: "#f7f9ff",
                      fontWeight: 600,
                    },
                    "& .MuiListItemText-secondary": {
                      color: "#8fa0c5",
                    },
                  }}
                />
              </ListItemButton>
            </ListItem>
          ))}
        </List>
      ) : null}
    </Box>
  );
}

export default GrammarStartPanel;
