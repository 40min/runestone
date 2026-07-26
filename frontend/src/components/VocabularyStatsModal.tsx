import React from "react";
import { Box, Drawer, Typography } from "@mui/material";
import { useVocabularyDistribution } from "../hooks/useVocabulary";
import type { VocabularyStats } from "../hooks/useVocabulary";
import { ErrorAlert, LoadingSpinner } from "./ui";
import {
  buildLearnedDistributionGradient,
  LEARNED_COLORS,
} from "./vocabulary/visualization";
import VocabularyOverview from "./vocabulary/VocabularyOverview";

interface VocabularyStatsModalProps {
  open: boolean;
  onClose: () => void;
  stats: VocabularyStats | null;
  statsLoading: boolean;
  statsError: string | null;
}

const PRIORITY_COLORS = [
  "#b91c1c",
  "#ef4444",
  "#ff5a5f",
  "#f97316",
  "#fb923c",
  "#fbbf24",
  "#fde047",
  "#bef264",
  "#86efac",
  "#4ade80",
];

const PRIORITY_NAMES = [
  "Highest",
  "Very high",
  "High",
  "Above average",
  "Average",
  "Below average",
  "Low",
  "Very low",
  "Minimal",
  "Default",
];

const learnedLabel = (label: string) => {
  const normalized = label.toLowerCase();
  if (normalized.includes("never")) return "Never learned";
  if (normalized.includes("1") && normalized.includes("10")) return "1–10 times";
  if (normalized.includes("11") && normalized.includes("30")) return "11–30 times";
  if (normalized.includes(">30") || normalized.includes("over")) return "Over 30";
  return label;
};

const VocabularyStatsModal: React.FC<VocabularyStatsModalProps> = ({
  open,
  onClose,
  stats,
  statsLoading,
  statsError,
}) => {
  const { data, loading, error } = useVocabularyDistribution(open);
  const priorities = data?.priority_distribution ?? [];
  const learned = data?.learned_times_distribution ?? [];
  const priorityTotal = priorities.reduce((sum, item) => sum + item.count, 0);
  const learnedTotal = learned.reduce((sum, item) => sum + item.count, 0);
  const total = Math.max(priorityTotal, learnedTotal);
  const neverLearned = learned.find((item) =>
    item.label.toLowerCase().includes("never")
  )?.count ?? 0;
  const unseenPercentage = learnedTotal
    ? Math.round((neverLearned / learnedTotal) * 100)
    : 0;
  const maximumPriorityCount = Math.max(
    ...priorities.map((item) => item.count),
    0
  );
  const allEmpty = data !== null && total === 0;
  const showLoading = loading || (!data && !error);
  const learnedGradient = buildLearnedDistributionGradient(
    learned.map((item) => item.count)
  );

  return (
    <Drawer
      anchor="right"
      open={open}
      onClose={(_, reason) => {
        if (reason === "backdropClick" || reason === "escapeKeyDown") {
          onClose();
        }
      }}
      aria-labelledby="vocab-stats-title"
      ModalProps={{
        slotProps: {
          backdrop: {
            sx: {
              backgroundColor: "rgba(2, 6, 24, 0.78)",
              backdropFilter: "blur(3px)",
            },
          },
        },
      }}
      PaperProps={{
        "aria-labelledby": "vocab-stats-title",
        onClick: onClose,
        sx: {
          width: "min(650px, 94vw)",
          color: "#f4f7ff",
          cursor: "pointer",
          borderLeft: "1px solid rgba(103, 121, 181, 0.52)",
          background:
            "linear-gradient(155deg, rgba(18, 26, 65, 0.99), rgba(7, 12, 43, 0.99) 68%)",
          boxShadow: "-28px 0 90px rgba(0, 0, 0, 0.48)",
        },
      }}
    >
      <Box
        component="header"
        sx={{
          display: "flex",
          alignItems: "flex-start",
          gap: 2,
          px: { xs: 2.5, sm: 4 },
          py: { xs: 2.5, sm: 3.5 },
          borderBottom: "1px solid rgba(99, 114, 173, 0.35)",
        }}
      >
        <Box>
          <Typography
            id="vocab-stats-title"
            component="h2"
            sx={{ fontSize: "1.35rem", fontWeight: 700, letterSpacing: "-0.025em" }}
          >
            Vocabulary statistics
          </Typography>
          <Typography sx={{ color: "#99a8ca", fontSize: "0.78rem", mt: 0.6 }}>
            A clearer view of what is active, learned, and waiting.
          </Typography>
        </Box>
      </Box>

      <Box sx={{ px: { xs: 2.5, sm: 4 }, py: 3.5 }}>
        <Box sx={{ mb: 2.5 }}>
          {statsError
            ? <ErrorAlert message={statsError} />
            : <VocabularyOverview stats={stats} loading={statsLoading} compact />}
        </Box>
        {showLoading && <LoadingSpinner />}
        {!showLoading && error && <ErrorAlert message={error} />}

        {!showLoading && !error && allEmpty && (
          <Box sx={{ textAlign: "center", py: 8 }}>
            <Typography sx={{ color: "#c4cee8", mb: 1 }}>
              No vocabulary data yet
            </Typography>
            <Typography sx={{ color: "#7180a7", fontSize: "0.78rem" }}>
              Add words to your active vocabulary to see statistics here.
            </Typography>
          </Box>
        )}

        {!showLoading && !error && !allEmpty && data && (
          <>
            {/* ── Card 1: total words + learning history ─────────────── */}
            <Box
              component="section"
              aria-labelledby="learning-history-title"
              sx={{
                mb: 2.25,
                borderRadius: 2,
                border: "1px solid rgba(103, 121, 181, 0.44)",
                background:
                  "radial-gradient(circle at 10% 8%, rgba(35, 50, 116, 0.52), rgba(7, 11, 39, 0.92))",
                overflow: "hidden",
              }}
            >
            {/* ── Header: total words + unseen donut ─────────────────── */}
            <Box
              sx={{
                display: "grid",
                gridTemplateColumns: "1fr auto",
                alignItems: "center",
                gap: 2,
                px: 2.5,
                py: 2,
              }}
            >
              <Box>
                <Typography
                  sx={{
                    color: "#f4f7ff",
                    fontSize: "1.75rem",
                    fontWeight: 700,
                    lineHeight: 1,
                    letterSpacing: "-0.045em",
                    fontVariantNumeric: "tabular-nums",
                  }}
                >
                  {total.toLocaleString()}
                </Typography>
                <Typography sx={{ color: "#8d9bc0", fontSize: "0.68rem", mt: 0.65 }}>
                  words included in these distributions
                </Typography>
              </Box>
              <Box
                aria-label={`${unseenPercentage}% unseen`}
                sx={{
                  width: 80,
                  height: 80,
                  borderRadius: "50%",
                  display: "grid",
                  placeItems: "center",
                  position: "relative",
                  background: learnedGradient,
                  "&::after": {
                    content: '""',
                    position: "absolute",
                    inset: 12,
                    borderRadius: "50%",
                    backgroundColor: "#0d1534",
                  },
                }}
              >
                <Box sx={{ position: "relative", zIndex: 1, textAlign: "center" }}>
                  <Typography sx={{ fontSize: "0.8rem", fontWeight: 700, lineHeight: 1 }}>
                    {unseenPercentage}%
                  </Typography>
                  <Typography sx={{ color: "#8795b9", fontSize: "0.54rem", mt: 0.3 }}>
                    unseen
                  </Typography>
                </Box>
              </Box>
            </Box>

            {/* ── Learning history ──────────────────────────────────── */}
            <Box
              component="section"
              aria-labelledby="learning-history-title"
              sx={{
                px: 2.5,
                py: 2,
                borderTop: "1px solid rgba(99, 114, 173, 0.28)",
              }}
            >
              <Typography id="learning-history-title" sx={{ fontSize: "0.82rem", fontWeight: 700, mb: 0.4 }}>
                Learning history
              </Typography>
              <Typography sx={{ color: "#7583aa", fontSize: "0.65rem", mb: 1.5 }}>
                How many times each word has been reviewed.
              </Typography>

              {learnedTotal === 0 ? (
                <Typography sx={{ color: "#7180a7", fontSize: "0.75rem" }}>
                  No data yet
                </Typography>
              ) : (
                <Box sx={{ display: "grid", gridTemplateColumns: "repeat(2, 1fr)", gap: 1.1 }}>
                  {learned.map((item, index) => (
                    <Box key={item.label} sx={{ display: "flex", alignItems: "center", gap: 1 }}>
                      <Box
                        aria-hidden="true"
                        sx={{
                          width: 7,
                          height: 7,
                          borderRadius: "50%",
                          backgroundColor: LEARNED_COLORS[index % LEARNED_COLORS.length],
                          opacity: item.count === 0 ? 0.35 : 1,
                        }}
                      />
                      <Typography sx={{ color: "#aab7d4", fontSize: "0.7rem" }}>
                        {learnedLabel(item.label)}
                      </Typography>
                      <Typography
                        sx={{ ml: "auto", color: "#e1e7f8", fontSize: "0.7rem", fontWeight: 700, fontVariantNumeric: "tabular-nums" }}
                      >
                        {item.count.toLocaleString()}
                      </Typography>
                    </Box>
                  ))}
                </Box>
              )}
            </Box>

            </Box>

            {/* ── Card 2: priority distribution ──────────────────────── */}
            <Box
              component="section"
              aria-labelledby="priority-distribution-title"
              sx={{
                p: 2.5,
                borderRadius: 2,
                border: "1px solid rgba(99, 114, 173, 0.34)",
                backgroundColor: "rgba(255,255,255,.02)",
              }}
            >
              <Typography id="priority-distribution-title" sx={{ fontSize: "0.82rem", fontWeight: 700, mb: 0.4 }}>
                Priority distribution
              </Typography>
              <Typography sx={{ color: "#7583aa", fontSize: "0.65rem", mb: 1.5 }}>
                Relative count across the ten priority levels.
              </Typography>

              {priorities.map((item) => {
                const priority = Math.min(Math.max(item.priority, 0), 9);
                const width = maximumPriorityCount
                  ? (item.count / maximumPriorityCount) * 100
                  : 0;

                return (
                  <Box
                    key={item.priority}
                    sx={{
                      display: "grid",
                      gridTemplateColumns: "120px 1fr 44px",
                      alignItems: "center",
                      gap: 1.25,
                      my: 1,
                    }}
                  >
                    <Box sx={{ display: "flex", alignItems: "center", gap: 0.9, minWidth: 0 }}>
                      <Box
                        aria-hidden="true"
                        sx={{ width: 7, height: 7, flexShrink: 0, borderRadius: "50%", backgroundColor: PRIORITY_COLORS[priority] }}
                      />
                      <Typography sx={{ color: "#aab7d4", fontSize: "0.67rem", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
                        {PRIORITY_NAMES[priority]} · {priority}
                      </Typography>
                    </Box>
                    <Box sx={{ height: 6, overflow: "hidden", borderRadius: 99, backgroundColor: "rgba(127,148,205,.12)" }}>
                      <Box
                        data-testid={`priority-bar-${priority}`}
                        data-color={PRIORITY_COLORS[priority]}
                        sx={{
                          width: item.count > 0 ? `${Math.max(width, 1)}%` : 0,
                          height: "100%",
                          borderRadius: "inherit",
                          backgroundColor: PRIORITY_COLORS[priority],
                        }}
                      />
                    </Box>
                    <Typography sx={{ color: "#8290b5", fontSize: "0.67rem", textAlign: "right", fontVariantNumeric: "tabular-nums" }}>
                      {item.count.toLocaleString()}
                    </Typography>
                  </Box>
                );
              })}
            </Box>
          </>
        )}
      </Box>
    </Drawer>
  );
};

export default VocabularyStatsModal;
