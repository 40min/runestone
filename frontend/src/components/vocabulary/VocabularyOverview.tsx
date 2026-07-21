import React from "react";
import { Box, Typography } from "@mui/material";
import type { VocabularyStats } from "../../hooks/useVocabulary";
import { getActiveSegmentCount } from "./visualization";

interface VocabularyOverviewProps {
  stats: VocabularyStats | null;
  loading: boolean;
}

interface MetricDefinition {
  key: keyof VocabularyStats;
  label: string;
  note: (stats: VocabularyStats) => string;
}

const metricDefinitions: MetricDefinition[] = [
  {
    key: "words_in_learn_count",
    label: "Words Studied",
    note: (stats) => {
      const percentage = getPercentage(
        stats.words_in_learn_count,
        stats.overall_words_count
      );
      return `${percentage}% of your ${formatNumber(stats.overall_words_count)} saved words`;
    },
  },
  {
    key: "words_skipped_count",
    label: "Words Skipped",
    note: () => "Not currently in your study flow",
  },
  {
    key: "overall_words_count",
    label: "Overall Words",
    note: () => "Your complete saved vocabulary",
  },
  {
    key: "words_prioritized_count",
    label: "Prioritised Words",
    note: (stats) =>
      `${getPercentage(stats.words_prioritized_count, stats.overall_words_count)}% ready for focused review`,
  },
];

const formatNumber = (value: number) => value.toLocaleString();

const getPercentage = (value: number, total: number) =>
  total > 0 ? Math.round((value / total) * 100) : 0;

const metricBorder = "1px solid rgba(103, 121, 181, 0.32)";

const VocabularyOverview: React.FC<VocabularyOverviewProps> = ({
  stats,
  loading,
}) => {
  const studiedPercentage = stats
    ? getPercentage(stats.words_in_learn_count, stats.overall_words_count)
    : 0;

  return (
    <Box
      component="section"
      aria-label="Vocabulary overview"
      sx={{
        display: "grid",
        gridTemplateColumns: {
          xs: "1fr",
          sm: "repeat(2, minmax(0, 1fr))",
          lg: "1.35fr repeat(3, minmax(0, 1fr))",
        },
        overflow: "hidden",
        border: metricBorder,
        borderRadius: 2.25,
        background:
          "radial-gradient(circle at 5% 10%, rgba(31, 49, 113, 0.72), rgba(8, 13, 47, 0.94) 48%)",
      }}
    >
      {metricDefinitions.map((metric, index) => {
        const value = stats?.[metric.key] ?? 0;
        const activeSegments = getActiveSegmentCount(
          value,
          stats?.overall_words_count ?? 0
        );

        return (
          <Box
            component="article"
            key={metric.key}
            sx={{
              minHeight: 138,
              p: { xs: 2.25, md: 2.75 },
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              gap: 2,
              borderLeft: {
                xs: 0,
                sm: index % 2 === 1 ? metricBorder : 0,
                lg: index > 0 ? metricBorder : 0,
              },
              borderTop: {
                xs: index > 0 ? metricBorder : 0,
                sm: index > 1 ? metricBorder : 0,
                lg: 0,
              },
            }}
          >
            <Box sx={{ minWidth: 0 }}>
              <Typography
                sx={{ color: "#a8b6d8", fontSize: "0.78rem", mb: 0.8 }}
              >
                {metric.label}
              </Typography>
              <Typography
                sx={{
                  color: "#f4f7ff",
                  fontSize: { xs: "1.75rem", md: "2rem" },
                  fontWeight: 700,
                  letterSpacing: "-0.04em",
                  lineHeight: 1,
                  fontVariantNumeric: "tabular-nums",
                }}
              >
                {loading || !stats ? "…" : formatNumber(value)}
              </Typography>
              <Typography
                sx={{ color: "#7f8db2", fontSize: "0.72rem", mt: 1.1 }}
              >
                {stats ? metric.note(stats) : "Loading vocabulary summary"}
              </Typography>

              {index > 0 && metric.key !== "overall_words_count" && (
                <Box
                  aria-hidden="true"
                  data-testid={`${metric.key}-segments`}
                  sx={{
                    display: "grid",
                    gridTemplateColumns: "repeat(6, 1fr)",
                    gap: 0.5,
                    mt: 1.75,
                  }}
                >
                  {Array.from({ length: 6 }, (_, segment) => (
                    <Box
                      key={segment}
                      sx={{
                        height: 3,
                        borderRadius: 99,
                        backgroundColor:
                          segment < activeSegments
                            ? "#38e07b"
                            : "rgba(56, 224, 123, 0.16)",
                      }}
                    />
                  ))}
                </Box>
              )}
            </Box>

            {index === 0 && (
              <Box
                aria-label={`${studiedPercentage}% of vocabulary studied`}
                sx={{
                  width: 76,
                  height: 76,
                  flexShrink: 0,
                  borderRadius: "50%",
                  display: "grid",
                  placeItems: "center",
                  background: `conic-gradient(#38e07b ${studiedPercentage}%, rgba(56, 224, 123, 0.13) 0)`,
                  position: "relative",
                  "&::after": {
                    content: '""',
                    position: "absolute",
                    inset: 10,
                    borderRadius: "50%",
                    backgroundColor: "#10183d",
                  },
                }}
              >
                <Typography
                  sx={{
                    position: "relative",
                    zIndex: 1,
                    color: "#f4f7ff",
                    fontWeight: 700,
                    fontSize: "0.78rem",
                  }}
                >
                  {studiedPercentage}%
                </Typography>
              </Box>
            )}
          </Box>
        );
      })}
    </Box>
  );
};

export default VocabularyOverview;
