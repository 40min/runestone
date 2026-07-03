import React from "react";
import {
  Dialog,
  DialogTitle,
  DialogContent,
  Box,
  IconButton,
  Typography,
} from "@mui/material";
import CloseIcon from "@mui/icons-material/Close";
import { PieChart, Pie, Cell, Tooltip, ResponsiveContainer } from "recharts";
import { useVocabularyDistribution } from "../hooks/useVocabulary";
import type {
  PriorityDistributionItem,
  LearnedTimesDistributionItem,
} from "../hooks/useVocabulary";
import { LoadingSpinner, ErrorAlert } from "./ui";

// ─── Colour palettes ────────────────────────────────────────────────────────

/** 10-step gradient: red alert (highest priority 0) → green (lowest priority 9) */
const PRIORITY_COLORS = [
  "#991b1b", // 0 Highest
  "#dc2626", // 1 Very High
  "#ef4444", // 2 High
  "#f97316", // 3 Above Average
  "#fb923c", // 4 Average
  "#fbbf24", // 5 Below Average
  "#fde047", // 6 Low
  "#bef264", // 7 Very Low
  "#86efac", // 8 Minimal
  "#4ade80", // 9 Default
];

const LEARNED_COLORS = ["#6366f1", "#22d3ee", "#a78bfa", "#34d399"];

// ─── Shared sub-components ──────────────────────────────────────────────────

interface ChartEntry {
  label: string;
  count: number;
}

interface LegendItemProps {
  color: string;
  label: string;
  count: number;
}

const LegendItem: React.FC<LegendItemProps> = ({ color, label, count }) => (
  <Box sx={{ display: "flex", alignItems: "center", gap: 1, py: 0.25 }}>
    <Box
      sx={{
        width: 10,
        height: 10,
        borderRadius: "50%",
        backgroundColor: color,
        flexShrink: 0,
        opacity: count === 0 ? 0.35 : 1,
      }}
    />
    <Typography
      sx={{
        color:
          count === 0 ? "rgba(255,255,255,0.4)" : "rgba(255,255,255,0.85)",
        fontSize: "0.75rem",
        lineHeight: 1.4,
      }}
    >
      {label}
    </Typography>
    <Typography
      sx={{
        color:
          count === 0 ? "rgba(255,255,255,0.3)" : "rgba(255,255,255,0.7)",
        fontSize: "0.75rem",
        ml: "auto",
        pl: 1,
      }}
    >
      {count}
    </Typography>
  </Box>
);

interface DonutChartProps {
  title: string;
  items: ChartEntry[];
  colors: string[];
  ariaLabel: string;
}

const DonutChart: React.FC<DonutChartProps> = ({
  title,
  items,
  colors,
  ariaLabel,
}) => {
  const total = items.reduce((s, i) => s + i.count, 0);
  const pieData = items.filter((i) => i.count > 0);
  const allZero = total === 0;

  return (
    <Box
      sx={{
        flex: 1,
        minWidth: { xs: "100%", sm: 280 },
        p: 2,
        borderRadius: 2,
        background:
          "linear-gradient(180deg, rgba(255,255,255,0.06) 0%, rgba(255,255,255,0.02) 100%)",
        border: "1px solid rgba(255,255,255,0.08)",
      }}
    >
      <Typography
        sx={{
          color: "rgba(255,255,255,0.9)",
          fontWeight: 600,
          fontSize: "0.875rem",
          mb: 1.5,
          textAlign: "center",
        }}
      >
        {title}
      </Typography>

      {allZero ? (
        <Box sx={{ textAlign: "center", py: 3 }}>
          <Typography
            sx={{ color: "rgba(255,255,255,0.4)", fontSize: "0.8rem" }}
          >
            No data yet
          </Typography>
        </Box>
      ) : (
        <Box sx={{ position: "relative", width: "100%", height: 180 }}>
          <ResponsiveContainer width="100%" height="100%">
            <PieChart aria-label={ariaLabel}>
              <Pie
                data={pieData}
                dataKey="count"
                nameKey="label"
                cx="50%"
                cy="50%"
                innerRadius={52}
                outerRadius={78}
                paddingAngle={2}
                isAnimationActive
              >
                {pieData.map((entry) => {
                  const idx = items.findIndex((i) => i.label === entry.label);
                  return (
                    <Cell
                      key={entry.label}
                      fill={colors[idx % colors.length]}
                    />
                  );
                })}
              </Pie>
              <Tooltip
                contentStyle={{
                  backgroundColor: "rgba(17,24,39,0.92)",
                  border: "1px solid rgba(255,255,255,0.12)",
                  borderRadius: 8,
                  color: "#fff",
                  fontSize: 13,
                }}
                formatter={(value, name) => {
                  const count = Number(value ?? 0);
                  return [
                    `${count} word${count !== 1 ? "s" : ""}`,
                    String(name),
                  ];
                }}
              />
            </PieChart>
          </ResponsiveContainer>
          {/* Centred total */}
          <Box
            sx={{
              position: "absolute",
              top: "50%",
              left: "50%",
              transform: "translate(-50%, -50%)",
              textAlign: "center",
              pointerEvents: "none",
            }}
          >
            <Typography
              sx={{
                color: "white",
                fontWeight: 700,
                fontSize: "1.3rem",
                lineHeight: 1,
              }}
            >
              {total}
            </Typography>
            <Typography
              sx={{ color: "rgba(255,255,255,0.5)", fontSize: "0.65rem" }}
            >
              words
            </Typography>
          </Box>
        </Box>
      )}

      {/* Custom legend — always shows all buckets including zero-count */}
      <Box sx={{ mt: 1.5 }}>
        {items.map((item, idx) => (
          <LegendItem
            key={item.label}
            color={colors[idx % colors.length]}
            label={item.label}
            count={item.count}
          />
        ))}
      </Box>
    </Box>
  );
};

// ─── Modal ───────────────────────────────────────────────────────────────────

interface VocabularyStatsModalProps {
  open: boolean;
  onClose: () => void;
}

const VocabularyStatsModal: React.FC<VocabularyStatsModalProps> = ({
  open,
  onClose,
}) => {
  const { data, loading, error } = useVocabularyDistribution(open);

  const priorityItems: ChartEntry[] = (
    data?.priority_distribution ?? []
  ).map((item: PriorityDistributionItem) => ({
    label: item.label,
    count: item.count,
  }));

  const learnedItems: ChartEntry[] = (
    data?.learned_times_distribution ?? []
  ).map((item: LearnedTimesDistributionItem) => ({
    label: item.label,
    count: item.count,
  }));

  const allEmpty =
    data !== null &&
    priorityItems.every((i) => i.count === 0) &&
    learnedItems.every((i) => i.count === 0);
  const showLoading = loading || (!data && !error);

  return (
    <Dialog
      open={open}
      onClose={onClose}
      maxWidth="md"
      fullWidth
      aria-labelledby="vocab-stats-title"
      PaperProps={{
        sx: {
          background:
            "linear-gradient(135deg, rgba(17,24,39,0.97) 0%, rgba(31,41,55,0.97) 100%)",
          backdropFilter: "blur(20px)",
          border: "1px solid rgba(255,255,255,0.1)",
          borderRadius: 3,
          color: "white",
        },
      }}
    >
      <DialogTitle
        id="vocab-stats-title"
        sx={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          pb: 1,
        }}
      >
        <Typography sx={{ fontWeight: 700, fontSize: "1.05rem" }}>
          Vocabulary Statistics
        </Typography>
        <IconButton
          onClick={onClose}
          aria-label="Close vocabulary statistics"
          size="small"
          sx={{ color: "rgba(255,255,255,0.6)" }}
        >
          <CloseIcon fontSize="small" />
        </IconButton>
      </DialogTitle>

      <DialogContent>
        {showLoading && <LoadingSpinner />}

        {!showLoading && error && <ErrorAlert message={error} />}

        {!showLoading && !error && allEmpty && (
          <Box sx={{ textAlign: "center", py: 6 }}>
            <Typography sx={{ color: "rgba(255,255,255,0.5)", mb: 1 }}>
              No vocabulary data yet
            </Typography>
            <Typography
              sx={{ color: "rgba(255,255,255,0.3)", fontSize: "0.8rem" }}
            >
              Add words to your active vocabulary to see statistics here.
            </Typography>
          </Box>
        )}

        {!showLoading && !error && !allEmpty && data && (
          <Box
            sx={{
              display: "flex",
              gap: 2,
              flexDirection: { xs: "column", sm: "row" },
              pt: 1,
              pb: 2,
            }}
          >
            <DonutChart
              title="Words by Priority"
              items={priorityItems}
              colors={PRIORITY_COLORS}
              ariaLabel="Priority distribution donut chart"
            />
            <DonutChart
              title="Words by Times Learned"
              items={learnedItems}
              colors={LEARNED_COLORS}
              ariaLabel="Learned-times distribution donut chart"
            />
          </Box>
        )}
      </DialogContent>
    </Dialog>
  );
};

export default VocabularyStatsModal;
