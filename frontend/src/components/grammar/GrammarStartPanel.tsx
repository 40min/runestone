import {
  Box,
  List,
  ListItem,
  ListItemButton,
  ListItemText,
  Typography,
} from "@mui/material";
import type { GrammarSearchResult } from "../../hooks/useGrammar";
import { ErrorAlert, LoadingSpinner } from "../ui";
import SearchInput from "../ui/SearchInput";

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
    <Box>
      <Typography variant="h6" sx={{ color: "white", mb: 1 }}>
        Search grammar cheatsheets
      </Typography>
      <Typography sx={{ color: "#9ca3af", mb: 3 }}>
        Search for a grammar topic, or select a cheatsheet from the list.
      </Typography>
      <SearchInput
        value={searchQuery}
        onChange={(event) => onSearchQueryChange(event.target.value)}
        onSearch={onSearch}
        onClear={onClearSearch}
        placeholder="Search grammar topics..."
        sx={{ mb: 3, maxWidth: 560 }}
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
        <List disablePadding aria-label="Grammar search results">
          {searchResults.map((result) => (
            <ListItem key={result.path || result.url} disablePadding sx={{ mb: 1 }}>
              <ListItemButton
                onClick={() => onSelectSearchResult(result.path)}
                sx={{
                  border: "1px solid #374151",
                  borderRadius: "0.5rem",
                  backgroundColor: "#1f2937",
                  "&:hover": {
                    backgroundColor: "#243244",
                  },
                }}
              >
                <ListItemText
                  primary={result.title || result.path}
                  secondary={result.path}
                  sx={{
                    "& .MuiListItemText-primary": {
                      color: "white",
                    },
                    "& .MuiListItemText-secondary": {
                      color: "#9ca3af",
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
