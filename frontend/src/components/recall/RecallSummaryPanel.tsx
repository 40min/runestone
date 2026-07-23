import {
  Box,
  Chip,
  CircularProgress,
  Stack,
  Tooltip,
  Typography,
} from "@mui/material";
import {
  CheckCircleOutline,
  Refresh,
  ShieldOutlined,
} from "@mui/icons-material";
import { CustomButton, buildAnalyzerShellSx } from "../ui";

const REFRESH_TOOLTIP =
  "Refresh selection: lowers the priority of all current words and replaces the selection.";

interface RecallSummaryPanelProps {
  wordCount: number;
  configured: boolean;
  deliveryEnabled: boolean;
  refreshing: boolean;
  disabled: boolean;
  onRefresh: () => void;
}

const RecallSummaryPanel = ({
  wordCount,
  configured,
  deliveryEnabled,
  refreshing,
  disabled,
  onRefresh,
}: RecallSummaryPanelProps) => {
  const deliveryLabel = configured
    ? `Delivery ${deliveryEnabled ? "enabled" : "disabled"}`
    : "Not configured";

  return (
    <Box
      component="aside"
      aria-label="Recall session summary"
      sx={{
        ...buildAnalyzerShellSx(
          "radial-gradient(circle at 20% 8%, rgba(32, 48, 112, 0.54), rgba(7, 12, 42, 0.98))"
        ),
        p: { xs: 3, md: 4 },
        minHeight: { lg: 520 },
        display: "flex",
        flexDirection: "column",
        position: { lg: "sticky" },
        top: { lg: 96 },
      }}
    >
      <Typography
        sx={{
          color: "#9cadd4",
          fontSize: "0.78rem",
          fontWeight: 600,
          letterSpacing: "0.08em",
          textTransform: "uppercase",
        }}
      >
        Next session
      </Typography>

      <Stack
        direction="row"
        alignItems="baseline"
        spacing={1.25}
        sx={{ mt: 2.5 }}
      >
        <Typography
          sx={{
            color: "#f8fafc",
            fontSize: { xs: "4rem", md: "4.5rem" },
            fontWeight: 700,
            letterSpacing: "-0.06em",
            lineHeight: 0.95,
          }}
        >
          {wordCount}
        </Typography>
        <Typography
          sx={{
            color: "#f8fafc",
            fontSize: { xs: "1.6rem", md: "1.8rem" },
            fontWeight: 700,
          }}
        >
          {wordCount === 1 ? "word" : "words"}
        </Typography>
      </Stack>

      <Chip
        icon={deliveryEnabled ? <CheckCircleOutline /> : undefined}
        label={deliveryLabel}
        variant="outlined"
        sx={{
          alignSelf: "flex-start",
          mt: 3,
          height: 42,
          px: 1,
          color: deliveryEnabled ? "#51e58e" : "#b7c2dd",
          borderColor: deliveryEnabled
            ? "rgba(81,229,142,0.86)"
            : "rgba(155,171,211,0.38)",
          fontSize: "0.95rem",
          "& .MuiChip-icon": {
            color: "inherit",
          },
        }}
      />

      <Typography
        sx={{
          color: "#bdc9e4",
          fontSize: "0.98rem",
          lineHeight: 1.65,
          mt: 3.5,
        }}
      >
        {configured
          ? "Your queue is ready for the next scheduled session."
          : "Connect Recall to prepare your next scheduled session."}
      </Typography>

      <Tooltip title={REFRESH_TOOLTIP}>
        <span>
          <CustomButton
            type="button"
            fullWidth
            size="large"
            startIcon={
              refreshing ? (
                <CircularProgress size={20} color="inherit" />
              ) : (
                <Refresh fontSize="small" />
              )
            }
            disabled={disabled}
            onClick={onRefresh}
            aria-label="Refresh selection"
            sx={{
              mt: 4.5,
              minHeight: 54,
              fontSize: "1rem",
              boxShadow: "0 12px 28px rgba(56,224,123,0.16)",
              "&:hover": {
                transform: "translateY(-1px)",
                boxShadow: "0 16px 32px rgba(56,224,123,0.24)",
              },
            }}
          >
            Refresh selection
          </CustomButton>
        </span>
      </Tooltip>

      <Box
        sx={{
          mt: "auto",
          pt: 3.5,
          borderTop: "1px solid rgba(126,145,194,0.24)",
          display: "flex",
          alignItems: "center",
          gap: 1.25,
          color: "#9cadd4",
        }}
      >
        <ShieldOutlined fontSize="small" />
        <Typography sx={{ fontSize: "0.86rem" }}>
          Changes sync with Telegram.
        </Typography>
      </Box>
    </Box>
  );
};

export default RecallSummaryPanel;
