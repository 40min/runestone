import {
  Box,
  Chip,
  CircularProgress,
  IconButton,
  Stack,
  Tooltip,
  Typography,
} from "@mui/material";
import {
  InfoOutlined,
  Refresh,
  RemoveCircleOutline,
  Snooze,
} from "@mui/icons-material";
import { useRecall } from "../hooks/useRecall";
import {
  CustomButton,
  ErrorAlert,
  SectionTitle,
  Snackbar,
  SurfaceCard,
} from "./ui";

const REFRESH_TOOLTIP =
  "Refresh selection: lowers the priority of all current words and replaces the selection.";
const POSTPONE_TOOLTIP =
  "Postpone: moves this word out of the current selection and lowers its recall priority.";
const REMOVE_TOOLTIP =
  "Remove from learning: stops learning this word and removes it from the current selection.";

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
    <Box sx={{ py: { xs: 4, md: 8 }, maxWidth: 900, mx: "auto" }}>
      <Box
        sx={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          gap: 2,
          mb: 4,
        }}
      >
        <Box>
          <SectionTitle marginBottom={0}>Recall</SectionTitle>
          <Typography sx={{ color: "rgba(255,255,255,0.64)", mt: 0.75 }}>
            Manage the words selected for your next recall sessions.
          </Typography>
        </Box>
        <Tooltip title={REFRESH_TOOLTIP}>
          <span>
            <IconButton
              aria-label="Refresh selection"
              disabled={!recall.configured || isMutating}
              onClick={() => void refreshSelection()}
              sx={{
                color: "rgba(255,255,255,0.78)",
                border: "1px solid rgba(255,255,255,0.16)",
                borderRadius: 1.5,
                "&:hover": {
                  color: "white",
                  borderColor: "rgba(255,255,255,0.36)",
                  backgroundColor: "rgba(255,255,255,0.07)",
                },
              }}
            >
              {pendingAction?.type === "refresh" ? (
                <CircularProgress size={20} color="inherit" />
              ) : (
                <Refresh fontSize="small" />
              )}
            </IconButton>
          </span>
        </Tooltip>
      </Box>

      <SurfaceCard padding={2} sx={{ mb: 2 }}>
        <Box
          sx={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            gap: 2,
            flexWrap: "wrap",
          }}
        >
          <Box>
            <Typography
              sx={{
                color: "rgba(255,255,255,0.62)",
                fontSize: "0.76rem",
                textTransform: "uppercase",
                letterSpacing: "0.08em",
              }}
            >
              Selected words
            </Typography>
            <Typography sx={{ color: "white", fontSize: "1.7rem", fontWeight: 700 }}>
              {recall.words.length}
            </Typography>
          </Box>
          <Chip
            label={
              recall.configured
                ? `Delivery ${recall.delivery_enabled ? "enabled" : "disabled"}`
                : "Not configured"
            }
            color={
              recall.configured && recall.delivery_enabled
                ? "success"
                : "default"
            }
            variant="outlined"
            sx={{
              color: "rgba(255,255,255,0.78)",
              borderColor:
                recall.configured && recall.delivery_enabled
                  ? "rgba(52,211,153,0.55)"
                  : "rgba(255,255,255,0.2)",
            }}
          />
        </Box>
      </SurfaceCard>

      {!recall.configured ? (
        <SurfaceCard>
          <Stack alignItems="center" spacing={1.5} sx={{ textAlign: "center", py: 3 }}>
            <InfoOutlined sx={{ color: "rgba(255,255,255,0.58)", fontSize: 34 }} />
            <Typography variant="h6" sx={{ color: "white", fontWeight: 650 }}>
              Recall is not configured
            </Typography>
            <Typography sx={{ color: "rgba(255,255,255,0.66)", maxWidth: 560 }}>
              Link your Telegram username in Profile, then send{" "}
              <Box component="span" sx={{ color: "white", fontFamily: "monospace" }}>
                /start
              </Box>{" "}
              to the bot to create your recall selection.
            </Typography>
          </Stack>
        </SurfaceCard>
      ) : recall.words.length === 0 ? (
        <SurfaceCard>
          <Stack alignItems="center" spacing={1} sx={{ textAlign: "center", py: 3 }}>
            <Typography variant="h6" sx={{ color: "white", fontWeight: 650 }}>
              No words selected
            </Typography>
            <Typography sx={{ color: "rgba(255,255,255,0.66)" }}>
              There are currently no eligible vocabulary words for recall.
            </Typography>
          </Stack>
        </SurfaceCard>
      ) : (
        <Stack component="ol" spacing={1.25} sx={{ listStyle: "none", p: 0, m: 0 }}>
          {recall.words.map((word, index) => {
            const postponing =
              pendingAction?.type === "postpone" &&
              pendingAction.vocabularyId === word.id;
            const removing =
              pendingAction?.type === "remove" &&
              pendingAction.vocabularyId === word.id;

            return (
              <Box
                component="li"
                key={word.id}
              >
                <SurfaceCard
                  padding={2}
                  sx={{
                    "&:hover": { borderColor: "rgba(255,255,255,0.18)" },
                  }}
                >
                  <Box
                    sx={{
                      display: "grid",
                      gridTemplateColumns: "auto minmax(0, 1fr) auto",
                      gap: { xs: 1.25, sm: 2 },
                      alignItems: "center",
                    }}
                  >
                    <Typography
                      aria-hidden="true"
                      sx={{
                        color: "rgba(255,255,255,0.38)",
                        fontSize: "0.78rem",
                        fontWeight: 700,
                        width: 20,
                        textAlign: "center",
                      }}
                    >
                      {index + 1}
                    </Typography>
                    <Box sx={{ minWidth: 0 }}>
                      <Typography
                        sx={{
                          color: "white",
                          fontWeight: 700,
                          fontSize: { xs: "1rem", sm: "1.08rem" },
                          overflowWrap: "anywhere",
                        }}
                      >
                        {word.word_phrase}
                      </Typography>
                      {word.translation && (
                        <Typography
                          sx={{
                            color: "rgba(255,255,255,0.7)",
                            mt: 0.25,
                            overflowWrap: "anywhere",
                          }}
                        >
                          {word.translation}
                        </Typography>
                      )}
                      {word.example_phrase && (
                        <Typography
                          sx={{
                            color: "rgba(255,255,255,0.5)",
                            fontSize: "0.86rem",
                            fontStyle: "italic",
                            mt: 0.75,
                            overflowWrap: "anywhere",
                          }}
                        >
                          {word.example_phrase}
                        </Typography>
                      )}
                    </Box>
                    <Stack direction="row" spacing={0.5}>
                      <Tooltip title={POSTPONE_TOOLTIP}>
                        <span>
                          <IconButton
                            aria-label={`Postpone ${word.word_phrase}`}
                            disabled={isMutating}
                            onClick={() =>
                              void postponeWord(word.id, word.word_phrase)
                            }
                            size="small"
                            sx={{ color: "rgba(255,255,255,0.68)" }}
                          >
                            {postponing ? (
                              <CircularProgress size={18} color="inherit" />
                            ) : (
                              <Snooze fontSize="small" />
                            )}
                          </IconButton>
                        </span>
                      </Tooltip>
                      <Tooltip title={REMOVE_TOOLTIP}>
                        <span>
                          <IconButton
                            aria-label={`Remove ${word.word_phrase} from learning`}
                            disabled={isMutating}
                            onClick={() =>
                              void removeWord(word.id, word.word_phrase)
                            }
                            size="small"
                            sx={{
                              color: "rgba(248,113,113,0.72)",
                              "&:hover": {
                                color: "#fca5a5",
                                backgroundColor: "rgba(239,68,68,0.1)",
                              },
                            }}
                          >
                            {removing ? (
                              <CircularProgress size={18} color="inherit" />
                            ) : (
                              <RemoveCircleOutline fontSize="small" />
                            )}
                          </IconButton>
                        </span>
                      </Tooltip>
                    </Stack>
                  </Box>
                </SurfaceCard>
              </Box>
            );
          })}
        </Stack>
      )}

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
