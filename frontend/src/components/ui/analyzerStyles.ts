import type { SxProps, Theme } from "@mui/material";

export const analyzerShellBorder = "1px solid rgba(99, 114, 173, 0.35)";
export const analyzerShellShadow = "inset 0 1px 0 rgba(255,255,255,0.04)";
export const analyzerShellRadius = "1rem";

export const analyzerShellGradients = {
  emptyState:
    "radial-gradient(circle at 18% 16%, rgba(37, 48, 116, 0.52), rgba(7, 11, 41, 0.97))",
  processing:
    "radial-gradient(circle at 18% 16%, rgba(35, 49, 116, 0.5), rgba(7, 12, 43, 0.97))",
  results:
    "radial-gradient(circle at 14% 10%, rgba(34, 48, 112, 0.4), rgba(6, 11, 42, 0.97))",
  uploadCompact:
    "radial-gradient(circle at 12% 10%, rgba(36, 48, 114, 0.44), rgba(7, 12, 44, 0.97))",
  uploadFull:
    "radial-gradient(circle at 10% 8%, rgba(35, 50, 116, 0.42), rgba(7, 11, 39, 0.97))",
} as const;

export const analyzerSurfaceBackground = "rgba(40, 29, 56, 0.92)";
export const analyzerSurfaceBorder = "1px solid rgba(95, 76, 123, 0.82)";
export const analyzerSurfaceRadius = "0.9rem";

export const analyzerSurfaceCardSx: SxProps<Theme> = {
  backgroundColor: analyzerSurfaceBackground,
  borderRadius: analyzerSurfaceRadius,
  border: analyzerSurfaceBorder,
};

export const buildAnalyzerShellSx = (
  background: string,
  sx: SxProps<Theme> = {}
): SxProps<Theme> => ({
  borderRadius: analyzerShellRadius,
  border: analyzerShellBorder,
  background,
  boxShadow: analyzerShellShadow,
  ...sx,
});
