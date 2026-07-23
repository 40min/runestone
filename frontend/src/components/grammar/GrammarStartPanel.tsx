import { Box, Typography } from "@mui/material";

function GrammarStartPanel() {
  return (
    <Box sx={{ maxWidth: 720 }}>
      <Typography
        variant="h4"
        sx={{
          color: "#f7f9ff",
          mb: 1.25,
          fontSize: { xs: "1.65rem", sm: "2rem" },
          fontWeight: 700,
          letterSpacing: "-0.025em",
        }}
      >
        Search grammar cheatsheets
      </Typography>
      <Typography sx={{ maxWidth: 560, color: "#aab8d7", lineHeight: 1.7 }}>
        Search for a grammar topic, or select a cheatsheet from the list.
      </Typography>
    </Box>
  );
}

export default GrammarStartPanel;
