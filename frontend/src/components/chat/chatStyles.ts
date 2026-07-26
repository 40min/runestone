import type { SxProps, Theme } from "@mui/material";
import {
  analyzerShellGradients,
  buildAnalyzerShellSx,
} from "../ui/analyzerStyles";

export const chatPageBackground = "#060b26";

export const chatPanelSx: SxProps<Theme> = buildAnalyzerShellSx(
  analyzerShellGradients.results,
  {
    position: "relative",
    overflow: "hidden",
  },
);

export const chatControlsPanelSx: SxProps<Theme> = buildAnalyzerShellSx(
  "radial-gradient(circle at 50% 0%, rgba(37, 61, 126, 0.22), rgba(7, 13, 43, 0.96) 58%)",
  {
    boxShadow:
      "inset 0 1px 0 rgba(255,255,255,0.04), 0 18px 40px rgba(3, 7, 25, 0.18)",
  },
);
