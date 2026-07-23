import { Box, CircularProgress, Stack, Typography } from "@mui/material";
import { useRecall } from "../hooks/useRecall";
import {
  CustomButton,
  ErrorAlert,
  SectionTitle,
  Snackbar,
} from "./ui";
import RecallQueuePanel from "./recall/RecallQueuePanel";
import RecallSummaryPanel from "./recall/RecallSummaryPanel";

const RecallView = () => {
  const {
    recall,
    loading,
    pendingAction,
    error,
    success,
    refetch,
    refreshSelection,
    postponeWord,
    removeWord,
    clearFeedback,
  } = useRecall();
  const isMutating = pendingAction !== null;

  if (loading && recall === null) {
    return (
      <Box
        sx={{
          minHeight: 320,
          display: "grid",
          placeItems: "center",
          color: "rgba(255,255,255,0.7)",
        }}
      >
        <Stack alignItems="center" spacing={2}>
          <CircularProgress size={32} />
          <Typography>Loading recall selection…</Typography>
        </Stack>
      </Box>
    );
  }

  if (recall === null) {
    return (
      <Box sx={{ py: 8 }}>
        <ErrorAlert
          message={error ?? "Failed to load recall selection"}
          sx={{ mt: 0 }}
        />
        <Box sx={{ mt: 2, textAlign: "center" }}>
          <CustomButton
            type="button"
            variant="secondary"
            onClick={() => void refetch()}
          >
            Try again
          </CustomButton>
        </Box>
      </Box>
    );
  }

  return (
    <Box sx={{ py: { xs: 3, md: 5 } }}>
      <Box sx={{ mb: { xs: 4, md: 5 } }}>
        <SectionTitle
          variant="h2"
          marginBottom={0}
          sx={{
            color: "#f8fafc",
            fontSize: { xs: "2.35rem", sm: "3rem" },
            lineHeight: 1.05,
            letterSpacing: "-0.04em",
          }}
        >
          Recall Your Swedish Vocabulary
        </SectionTitle>
        <Typography
          sx={{
            color: "#b3bfd9",
            fontSize: { xs: "1rem", sm: "1.1rem" },
            lineHeight: 1.7,
            mt: 1.5,
          }}
        >
          Manage the words selected for your next recall sessions.
        </Typography>
      </Box>

      <Box
        sx={{
          display: "grid",
          gridTemplateColumns: { xs: "1fr", lg: "320px minmax(0, 1fr)" },
          gap: { xs: 2, lg: 3 },
          alignItems: "start",
        }}
      >
        <RecallSummaryPanel
          wordCount={recall.words.length}
          configured={recall.configured}
          deliveryEnabled={recall.delivery_enabled}
          refreshing={pendingAction?.type === "refresh"}
          disabled={!recall.configured || isMutating}
          onRefresh={() => void refreshSelection()}
        />
        <RecallQueuePanel
          configured={recall.configured}
          words={recall.words}
          pendingAction={pendingAction}
          isMutating={isMutating}
          onPostpone={(id, phrase) => void postponeWord(id, phrase)}
          onRemove={(id, phrase) => void removeWord(id, phrase)}
        />
      </Box>

      <Snackbar
        open={Boolean(success)}
        message={success ?? ""}
        severity="success"
        onClose={clearFeedback}
      />
      <Snackbar
        open={Boolean(error)}
        message={error ?? ""}
        severity="error"
        onClose={clearFeedback}
      />
    </Box>
  );
};

export default RecallView;
