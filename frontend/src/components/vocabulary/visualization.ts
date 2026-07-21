export const LEARNED_COLORS = ["#6366f1", "#22d3ee", "#a78bfa", "#34d399"];

export const buildLearnedDistributionGradient = (counts: number[]) => {
  const total = counts.reduce((sum, count) => sum + count, 0);
  if (total <= 0) return "rgba(127, 148, 205, 0.16)";

  let cumulativePercentage = 0;
  const segments = counts.map((count, index) => {
    const start = cumulativePercentage;
    cumulativePercentage += (count / total) * 100;
    return `${LEARNED_COLORS[index % LEARNED_COLORS.length]} ${start}% ${cumulativePercentage}%`;
  });

  return `conic-gradient(${segments.join(", ")})`;
};

export const getActiveSegmentCount = (value: number, total: number) => {
  if (value <= 0 || total <= 0) return 0;
  return Math.max(1, Math.round((value / total) * 6));
};
