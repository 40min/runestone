import { Box, Typography } from "@mui/material";
import { Copy, Link as LinkIcon } from "lucide-react";
import {
  CustomButton,
  LoadingSpinner,
  MarkdownDisplay,
  analyzerShellGradients,
  buildAnalyzerShellSx,
} from "../ui";

type GrammarContentPanelProps = {
  category: string | null;
  title: string | null;
  markdownContent: string | null;
  loading: boolean;
  hasError: boolean;
  onCopyMarkdown: () => void;
  onCopyLink: () => void;
};

/**
 * Reading surface for a selected grammar cheatsheet.
 *
 * The shell intentionally reuses the analyzer page's border, gradient, and
 * radius so both learning workflows feel like parts of the same application.
 */
function GrammarContentPanel({
  category,
  title,
  markdownContent,
  loading,
  hasError,
  onCopyMarkdown,
  onCopyLink,
}: GrammarContentPanelProps) {
  return (
    <Box
      component="article"
      sx={{
        minHeight: { xs: 360, lg: 620 },
        p: { xs: 2, sm: 3, lg: 4 },
        ...buildAnalyzerShellSx(analyzerShellGradients.results),
      }}
    >
      <Box
        sx={{
          display: "flex",
          flexDirection: { xs: "column", sm: "row" },
          alignItems: { xs: "stretch", sm: "center" },
          justifyContent: "space-between",
          gap: 2,
          mb: { xs: 3, md: 4 },
        }}
      >
        <Typography
          component="p"
          sx={{
            minWidth: 0,
            color: "#9aabd0",
            fontSize: "0.84rem",
            overflowWrap: "anywhere",
          }}
        >
          {category && category !== "General" ? (
            <>
              <Box component="span" sx={{ textTransform: "capitalize" }}>
                {category}
              </Box>
              <Box component="span" aria-hidden="true" sx={{ px: 1, color: "#65759d" }}>
                /
              </Box>
            </>
          ) : null}
          <Box component="span" sx={{ color: "#dbe5fb" }}>
            {title}
          </Box>
        </Typography>

        <Box sx={{ display: "flex", flexWrap: "wrap", gap: 1 }}>
          <CustomButton
            variant="secondary"
            size="small"
            startIcon={<Copy size={15} aria-hidden="true" />}
            onClick={onCopyMarkdown}
            sx={{
              minHeight: 38,
              color: "#dbe5fb",
              border: "1px solid rgba(103, 124, 184, 0.46)",
              backgroundColor: "rgba(7, 13, 43, 0.25)",
              "&:hover": {
                color: "white",
                borderColor: "rgba(132, 153, 214, 0.7)",
                backgroundColor: "rgba(31, 46, 91, 0.5)",
              },
            }}
          >
            Copy markdown
          </CustomButton>
          <CustomButton
            variant="secondary"
            size="small"
            startIcon={<LinkIcon size={15} aria-hidden="true" />}
            onClick={onCopyLink}
            sx={{
              minHeight: 38,
              color: "#dbe5fb",
              border: "1px solid rgba(103, 124, 184, 0.46)",
              backgroundColor: "rgba(7, 13, 43, 0.25)",
              "&:hover": {
                color: "white",
                borderColor: "rgba(132, 153, 214, 0.7)",
                backgroundColor: "rgba(31, 46, 91, 0.5)",
              },
            }}
          >
            Copy link
          </CustomButton>
        </Box>
      </Box>

      {loading ? (
        <LoadingSpinner />
      ) : markdownContent ? (
        <Box
          sx={{
            "& .markdown-content": {
              color: "#edf2ff",
              fontSize: { xs: "0.98rem", md: "1rem" },
              lineHeight: 1.72,
            },
            "& .markdown-content h1": {
              mt: 0,
              mb: 2.5,
              color: "#f7f9ff",
              fontSize: { xs: "2rem", md: "2.45rem" },
              lineHeight: 1.1,
              letterSpacing: "-0.035em",
            },
            "& .markdown-content h2": {
              mt: 3.5,
              color: "var(--primary-color)",
              fontSize: "0.82rem",
              fontWeight: 700,
              letterSpacing: "0.13em",
              textTransform: "uppercase",
            },
            "& .markdown-content h3": {
              mt: 3,
              color: "#f3f6ff",
              fontSize: "1.12rem",
            },
            "& .markdown-content blockquote": {
              m: "1.5rem 0",
              px: 2.25,
              py: 1.25,
              borderLeft: "3px solid var(--primary-color)",
              borderRadius: "0 0.65rem 0.65rem 0",
              color: "#dbe5fb",
              backgroundColor: "rgba(56, 224, 123, 0.07)",
            },
            "& .markdown-content table": {
              display: "block",
              maxWidth: "100%",
              overflowX: "auto",
              borderRadius: "0.7rem",
            },
          }}
        >
          <MarkdownDisplay markdownContent={markdownContent} />
        </Box>
      ) : (
        !hasError && (
          <Typography sx={{ color: "#9aabd0" }}>
            Failed to load cheatsheet content.
          </Typography>
        )
      )}
    </Box>
  );
}

export default GrammarContentPanel;
