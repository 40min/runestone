export const formatResponseTime = (responseTimeMs: number): string => {
  if (responseTimeMs < 1000) {
    return `${responseTimeMs} ms`;
  }

  const responseTimeSeconds = responseTimeMs / 1000;
  return responseTimeSeconds >= 10
    ? `${responseTimeSeconds.toFixed(0)} s`
    : `${responseTimeSeconds.toFixed(1)} s`;
};
