import React from "react";
import {
  Box,
  FormControlLabel,
  IconButton,
  Switch,
  Tooltip,
  Typography,
  useMediaQuery,
  useTheme,
} from "@mui/material";
import TrendingUpIcon from "@mui/icons-material/TrendingUp";
import ChevronRightIcon from "@mui/icons-material/ChevronRight";
import type { SavedVocabularyItem } from "../../hooks/useVocabulary";
import { SearchInput } from "../ui";

interface VocabularyLedgerProps {
  items: SavedVocabularyItem[];
  searchTerm: string;
  hasActiveSearch: boolean;
  preciseSearch: boolean;
  loading: boolean;
  loadingMore: boolean;
  hasMore: boolean;
  error: string | null;
  boostingItemIds: Set<number>;
  loadMoreSentinelRef: React.RefObject<HTMLDivElement | null>;
  onSearchTermChange: (value: string) => void;
  onSearch: () => void;
  onClearSearch: () => void;
  onPreciseSearchChange: (checked: boolean) => void;
  onItemClick: (item: SavedVocabularyItem) => void;
  onBoostPriority: (
    event: React.MouseEvent,
    item: SavedVocabularyItem
  ) => void;
}

const ledgerBorder = "1px solid rgba(99, 114, 173, 0.38)";

const priorityLabels = [
  "highest",
  "very high",
  "high",
  "above average",
  "average",
  "below average",
  "low",
  "very low",
  "minimal",
  "default",
];

const getPriorityLabel = (priority: number) =>
  priorityLabels[Math.min(Math.max(priority, 0), 9)];

const formatDate = (value: string | null | undefined) =>
  value ? new Date(value).toLocaleDateString() : "—";

const learningNote = (item: SavedVocabularyItem) => {
  if (item.learned_times === 0) return "Not learned yet";
  const times = `${item.learned_times} time${item.learned_times === 1 ? "" : "s"}`;
  return item.last_learned
    ? `Learned ${times} · ${formatDate(item.last_learned)}`
    : `Learned ${times}`;
};

const VocabularyLedger: React.FC<VocabularyLedgerProps> = ({
  items,
  searchTerm,
  hasActiveSearch,
  preciseSearch,
  loading,
  loadingMore,
  hasMore,
  error,
  boostingItemIds,
  loadMoreSentinelRef,
  onSearchTermChange,
  onSearch,
  onClearSearch,
  onPreciseSearchChange,
  onItemClick,
  onBoostPriority,
}) => {
  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down("md"));

  return (
    <Box
      component="section"
      aria-label="Vocabulary list"
      sx={{
        overflow: "hidden",
        border: ledgerBorder,
        borderRadius: 2.25,
        backgroundColor: "rgba(9, 15, 51, 0.86)",
        boxShadow: "inset 0 1px 0 rgba(255,255,255,0.025)",
      }}
    >
      <Box
        sx={{
          display: "flex",
          alignItems: { xs: "stretch", sm: "center" },
          flexDirection: { xs: "column", sm: "row" },
          gap: 1.25,
          p: { xs: 1.5, md: 2.25 },
          borderBottom: ledgerBorder,
        }}
      >
        <SearchInput
          value={searchTerm}
          onChange={(event) => onSearchTermChange(event.target.value)}
          placeholder="Search vocabulary..."
          onSearch={onSearch}
          onClear={onClearSearch}
          sx={{
            mb: 0,
            maxWidth: 650,
            flex: 1,
            "& .MuiButton-root": {
              minHeight: 48,
              backgroundColor: "transparent",
              color: "#e4eaff",
              border: ledgerBorder,
              "&:hover": {
                backgroundColor: "rgba(255,255,255,0.05)",
                transform: "none",
              },
            },
          }}
          inputSx={{
            "& .MuiOutlinedInput-root": {
              minHeight: 48,
              color: "#f4f7ff",
              backgroundColor: "rgba(7, 12, 43, 0.78)",
              borderRadius: 1.5,
              "& fieldset": { borderColor: "rgba(111, 133, 192, 0.52)" },
              "&:hover fieldset": { borderColor: "rgba(138, 158, 216, 0.72)" },
              "&.Mui-focused fieldset": { borderColor: "#38e07b" },
            },
            "& .MuiInputBase-input": {
              color: "#f4f7ff",
              WebkitTextFillColor: "#f4f7ff",
              caretColor: "#38e07b",
            },
            "& .MuiInputBase-input::placeholder": {
              color: "#9aa8c8",
              opacity: 0.72,
            },
          }}
        />
        <FormControlLabel
          label="Precise search"
          control={
            <Switch
              id="precise-search-checkbox"
              checked={preciseSearch}
              onChange={(event) => onPreciseSearchChange(event.target.checked)}
              size="small"
              sx={{
                "& .MuiSwitch-switchBase.Mui-checked": { color: "#38e07b" },
                "& .MuiSwitch-switchBase.Mui-checked + .MuiSwitch-track": {
                  backgroundColor: "#38e07b",
                },
                "& .MuiSwitch-track": { backgroundColor: "#7788b3" },
              }}
            />
          }
          sx={{
            m: 0,
            color: "#d1d9ed",
            whiteSpace: "nowrap",
            "& .MuiFormControlLabel-label": { fontSize: "0.78rem" },
          }}
        />
      </Box>

      {!isMobile && items.length > 0 && (
        <Box
          sx={{
            display: "grid",
            gridTemplateColumns:
              "minmax(190px, 1.1fr) minmax(280px, 1.65fr) minmax(140px, .68fr) minmax(210px, .95fr) 130px 38px",
            gap: 3,
            alignItems: "center",
            px: 2.75,
            py: 1.65,
            borderBottom: ledgerBorder,
          }}
        >
          {["Word", "Usage & grammar", "Study status", "Learning progress", "Updated", ""].map(
            (label, index) => (
              <Typography
                key={label || "actions"}
                sx={{
                  color: "#8493bb",
                  fontSize: "0.75rem",
                  fontWeight: 700,
                  letterSpacing: "0.08em",
                  textTransform: "uppercase",
                  justifySelf: index === 4 ? "center" : "start",
                  textAlign: index === 4 ? "center" : "left",
                  width: index === 4 ? "100%" : "auto",
                }}
              >
                {label}
              </Typography>
            )
          )}
        </Box>
      )}

      {items.length === 0 && !loading ? (
        <Box sx={{ textAlign: "center", px: 3, py: 8 }}>
          <Typography sx={{ color: "#c2cee8", mb: 1 }}>
            {hasActiveSearch
              ? "No vocabulary matches your search."
              : "No vocabulary saved yet."}
          </Typography>
          <Typography sx={{ color: "#7180a7", fontSize: "0.85rem" }}>
            {hasActiveSearch
              ? "Try a different search term."
              : "Analyze some text and save vocabulary items to see them here."}
          </Typography>
        </Box>
      ) : (
        items.map((item) => {
          const isHighestPriority = item.priority_learn <= 0;
          const isBoosting = boostingItemIds.has(item.id);

          return (
            <Box
              component="article"
              key={item.id}
              onClick={() => onItemClick(item)}
              sx={{
                display: "grid",
                gridTemplateColumns: {
                  xs: "1fr auto",
                  md: "minmax(190px, 1.1fr) minmax(280px, 1.65fr) minmax(140px, .68fr) minmax(210px, .95fr) 130px 38px",
                },
                gap: { xs: 2, md: 3 },
                alignItems: "center",
                minHeight: { xs: 0, md: 126 },
                px: { xs: 2, md: 2.75 },
                py: { xs: 2.25, md: 2 },
                borderBottom: ledgerBorder,
                cursor: "pointer",
                outline: "none",
                transition: "background-color 160ms ease, box-shadow 160ms ease",
                "&:hover": {
                  backgroundColor: "rgba(39, 51, 105, 0.22)",
                  boxShadow: "inset 3px 0 0 rgba(56, 224, 123, 0.72)",
                },
              }}
            >
              <Box sx={{ minWidth: 0 }}>
                <Typography
                  sx={{
                    color: "#f3f6ff",
                    fontWeight: 700,
                    fontSize: "1.1rem",
                    lineHeight: 1.25,
                    overflowWrap: "anywhere",
                  }}
                >
                  {item.word_phrase}
                </Typography>
                <Typography
                  sx={{ color: "#b8c4df", fontSize: "0.9rem", mt: 0.5 }}
                >
                  {item.translation}
                </Typography>
              </Box>

              <Box
                sx={{
                  minWidth: 0,
                  gridColumn: { xs: "1 / -1", md: "auto" },
                  gridRow: { xs: 2, md: "auto" },
                }}
              >
                <Typography
                  sx={{ color: "#e1e7f7", fontSize: "0.9rem", mb: 0.7 }}
                >
                  {item.example_phrase || "—"}
                </Typography>
                <Typography
                  sx={{ color: "#93a1c4", fontSize: "0.82rem", lineHeight: 1.5 }}
                >
                  {item.extra_info || "—"}
                </Typography>
              </Box>

              <Box sx={{ gridRow: { xs: 3, md: "auto" } }}>
                <Box
                  sx={{
                    display: "inline-flex",
                    alignItems: "center",
                    gap: 0.75,
                    px: 1.1,
                    py: 0.5,
                    borderRadius: 99,
                    color: item.in_learn ? "#65eaa0" : "#a8b3cf",
                    backgroundColor: item.in_learn
                      ? "rgba(56, 224, 123, 0.08)"
                      : "rgba(148, 163, 184, 0.08)",
                    border: item.in_learn
                      ? "1px solid rgba(56, 224, 123, 0.28)"
                      : "1px solid rgba(148, 163, 184, 0.22)",
                  }}
                >
                  <Box
                    aria-hidden="true"
                    sx={{
                      width: 6,
                      height: 6,
                      borderRadius: "50%",
                      backgroundColor: item.in_learn ? "#38e07b" : "#94a3b8",
                    }}
                  />
                  <Typography sx={{ fontSize: "0.76rem", fontWeight: 700 }}>
                    {item.in_learn ? "In Learning" : "Skipped"}
                  </Typography>
                </Box>
                <Typography sx={{ color: "#8290b3", fontSize: "0.76rem", mt: 0.7 }}>
                  {item.in_learn ? "Active queue" : "Outside study flow"}
                </Typography>
              </Box>

              <Box
                sx={{
                  gridRow: { xs: 3, md: "auto" },
                  width: { xs: 170, md: "auto" },
                  justifySelf: { xs: "end", md: "stretch" },
                }}
              >
                <Box sx={{ display: "flex", alignItems: "center", gap: 1 }}>
                  <Typography
                    sx={{ color: "#b6c2dd", fontSize: "0.8rem", flex: 1 }}
                  >
                    Priority{" "}
                    <Box
                      component="span"
                      sx={{
                        color: item.priority_learn <= 2 ? "#ffb14e" : "#aebbd9",
                        fontWeight: 700,
                      }}
                    >
                      {getPriorityLabel(item.priority_learn)} · {item.priority_learn}
                    </Box>
                  </Typography>
                  <Tooltip
                    title={
                      isBoosting
                        ? "Updating priority..."
                        : isHighestPriority
                          ? "Already highest priority"
                          : "Boost priority"
                    }
                  >
                    <span>
                      <IconButton
                        aria-label={`Boost priority for ${item.word_phrase}`}
                        size="small"
                        disabled={isHighestPriority || isBoosting}
                        onClick={(event) => onBoostPriority(event, item)}
                        sx={{
                          width: 30,
                          height: 30,
                          color: "#9fb2e8",
                          border: ledgerBorder,
                          borderRadius: 1,
                          "&:hover": { backgroundColor: "rgba(159,178,232,.1)" },
                          "&.Mui-disabled": {
                            color: "rgba(159,178,232,.3)",
                            borderColor: "rgba(99,114,173,.18)",
                          },
                        }}
                      >
                        <TrendingUpIcon sx={{ fontSize: 15 }} />
                      </IconButton>
                    </span>
                  </Tooltip>
                </Box>
                <Typography sx={{ color: "#8290b3", fontSize: "0.76rem", mt: 0.7 }}>
                  {learningNote(item)}
                </Typography>
              </Box>

              <Typography
                component="time"
                sx={{
                  color: "#aab6d3",
                  fontSize: "0.8rem",
                  display: { xs: "none", md: "block" },
                  justifySelf: "center",
                  textAlign: "center",
                  width: "100%",
                }}
              >
                {formatDate(item.updated || item.updated_at)}
              </Typography>

              <IconButton
                aria-label={`Edit ${item.word_phrase}`}
                onClick={(event) => {
                  event.stopPropagation();
                  onItemClick(item);
                }}
                sx={{
                  color: "#7482a8",
                  justifySelf: "end",
                  gridColumn: { xs: 2, md: "auto" },
                  gridRow: { xs: 1, md: "auto" },
                }}
              >
                <ChevronRightIcon fontSize="small" />
              </IconButton>
            </Box>
          );
        })
      )}

      {loading && (
        <Box sx={{ textAlign: "center", py: 1.5 }}>
          <Typography sx={{ color: "#8190b4", fontSize: "0.75rem" }}>
            Loading...
          </Typography>
        </Box>
      )}

      <Box
        ref={loadMoreSentinelRef}
        data-testid="vocabulary-load-more-sentinel"
        sx={{ height: 1 }}
      />

      <Box
        sx={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          gap: 2,
          px: 2.75,
          py: 1.4,
          color: "#7180a7",
        }}
      >
        <Typography sx={{ fontSize: "0.68rem" }}>
          {loadingMore
            ? "Loading more..."
            : hasMore
              ? "Loading more as you scroll"
              : items.length > 0
                ? "All vocabulary loaded."
                : "Ready"}
        </Typography>
        <Typography sx={{ fontSize: "0.68rem" }}>
          {items.length.toLocaleString()} shown
        </Typography>
      </Box>

      {error && items.length > 0 && (
        <Typography
          role="alert"
          sx={{ color: "#fda4af", textAlign: "center", px: 2, pb: 1.5, fontSize: "0.78rem" }}
        >
          {error}
        </Typography>
      )}
    </Box>
  );
};

export default VocabularyLedger;
