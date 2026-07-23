import {
  Box,
  CircularProgress,
  IconButton,
  Stack,
  Tooltip,
  Typography,
} from "@mui/material";
import {
  InfoOutlined,
  RemoveCircleOutline,
  Snooze,
} from "@mui/icons-material";
import type {
  RecallPendingAction,
  RecallWord,
} from "../../types/recall";
import { buildAnalyzerShellSx } from "../ui";

const POSTPONE_TOOLTIP =
  "Postpone: moves this word out of the current selection and lowers its recall priority.";
const REMOVE_TOOLTIP =
  "Remove from learning: stops learning this word and removes it from the current selection.";

interface RecallQueuePanelProps {
  configured: boolean;
  words: RecallWord[];
  pendingAction: RecallPendingAction | null;
  isMutating: boolean;
  onPostpone: (vocabularyId: number, wordPhrase: string) => void;
  onRemove: (vocabularyId: number, wordPhrase: string) => void;
}

const QueueEmptyState = ({ configured }: { configured: boolean }) => (
  <Stack
    alignItems="center"
    justifyContent="center"
    spacing={1.5}
    sx={{ minHeight: 360, px: 3, py: 7, textAlign: "center" }}
  >
    <InfoOutlined sx={{ color: "#8799c4", fontSize: 38 }} />
    <Typography
      component="h3"
      sx={{ color: "#f8fafc", fontSize: "1.35rem", fontWeight: 700 }}
    >
      {configured ? "No words selected" : "Recall is not configured"}
    </Typography>
    <Typography sx={{ color: "#aebbd8", maxWidth: 560, lineHeight: 1.7 }}>
      {configured ? (
        "There are currently no eligible vocabulary words for recall."
      ) : (
        <>
          Link your Telegram username in Profile, then send{" "}
          <Box
            component="span"
            sx={{ color: "#f8fafc", fontFamily: "monospace" }}
          >
            /start
          </Box>{" "}
          to the bot to create your recall selection.
        </>
      )}
    </Typography>
  </Stack>
);

const RecallQueuePanel = ({
  configured,
  words,
  pendingAction,
  isMutating,
  onPostpone,
  onRemove,
}: RecallQueuePanelProps) => (
  <Box
    component="section"
    aria-labelledby="recall-queue-title"
    sx={{
      ...buildAnalyzerShellSx(
        "radial-gradient(circle at 12% 5%, rgba(27, 42, 101, 0.46), rgba(6, 11, 40, 0.98))"
      ),
      overflow: "hidden",
      minWidth: 0,
    }}
  >
    <Box
      sx={{
        px: { xs: 2.25, sm: 3 },
        py: 2.5,
        borderBottom: "1px solid rgba(126,145,194,0.25)",
        display: "flex",
        alignItems: "baseline",
        gap: 1.5,
        flexWrap: "wrap",
      }}
    >
      <Typography
        id="recall-queue-title"
        component="h3"
        sx={{ color: "#f8fafc", fontSize: "1.3rem", fontWeight: 700 }}
      >
        Selected words
      </Typography>
      <Typography sx={{ color: "#9cadd4", fontSize: "0.92rem" }}>
        {words.length} in queue
      </Typography>
    </Box>

    {!configured || words.length === 0 ? (
      <QueueEmptyState configured={configured} />
    ) : (
      <Box component="ol" sx={{ listStyle: "none", p: 0, m: 0 }}>
        {words.map((word, index) => {
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
              sx={{
                display: "grid",
                gridTemplateColumns: {
                  xs: "24px minmax(0, 1fr) auto",
                  sm: "30px minmax(0, 1fr) auto",
                },
                alignItems: "center",
                gap: { xs: 1, sm: 2 },
                px: { xs: 2, sm: 3 },
                py: { xs: 2.25, sm: 2.75 },
                borderBottom:
                  index < words.length - 1
                    ? "1px solid rgba(126,145,194,0.24)"
                    : "none",
                transition: "background-color 160ms ease",
                "&:hover": {
                  backgroundColor: "rgba(88,109,174,0.07)",
                },
              }}
            >
              <Typography
                aria-hidden="true"
                sx={{
                  color: "#7181a9",
                  fontSize: "0.84rem",
                  fontWeight: 700,
                }}
              >
                {index + 1}
              </Typography>

              <Box sx={{ minWidth: 0 }}>
                <Stack
                  direction={{ xs: "column", sm: "row" }}
                  spacing={{ xs: 0.25, sm: 2 }}
                  alignItems={{ xs: "flex-start", sm: "baseline" }}
                >
                  <Typography
                    sx={{
                      color: "#f8fafc",
                      fontSize: "1.06rem",
                      fontWeight: 700,
                      overflowWrap: "anywhere",
                    }}
                  >
                    {word.word_phrase}
                  </Typography>
                  {word.translation && (
                    <Typography
                      sx={{
                        color: "#b8c4df",
                        fontSize: "0.92rem",
                        overflowWrap: "anywhere",
                      }}
                    >
                      {word.translation}
                    </Typography>
                  )}
                </Stack>
                {word.example_phrase && (
                  <Typography
                    sx={{
                      color: "#8999bd",
                      fontSize: "0.88rem",
                      fontStyle: "italic",
                      lineHeight: 1.55,
                      mt: 0.6,
                      overflowWrap: "anywhere",
                    }}
                  >
                    {word.example_phrase}
                  </Typography>
                )}
              </Box>

              <Stack direction="row" spacing={{ xs: 0, sm: 0.5 }}>
                <Tooltip title={POSTPONE_TOOLTIP}>
                  <span>
                    <IconButton
                      aria-label={`Postpone ${word.word_phrase}`}
                      disabled={isMutating}
                      onClick={() => onPostpone(word.id, word.word_phrase)}
                      sx={{
                        color: "#9dadd4",
                        border: "1px solid transparent",
                        "&:hover": {
                          color: "#dbe5ff",
                          borderColor: "rgba(156,173,216,0.34)",
                          backgroundColor: "rgba(101,124,190,0.12)",
                        },
                      }}
                    >
                      {postponing ? (
                        <CircularProgress size={20} color="inherit" />
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
                      onClick={() => onRemove(word.id, word.word_phrase)}
                      sx={{
                        color: "#ff656d",
                        border: "1px solid transparent",
                        "&:hover": {
                          color: "#ff848a",
                          borderColor: "rgba(255,101,109,0.34)",
                          backgroundColor: "rgba(255,83,93,0.09)",
                        },
                      }}
                    >
                      {removing ? (
                        <CircularProgress size={20} color="inherit" />
                      ) : (
                        <RemoveCircleOutline fontSize="small" />
                      )}
                    </IconButton>
                  </span>
                </Tooltip>
              </Stack>
            </Box>
          );
        })}
      </Box>
    )}
  </Box>
);

export default RecallQueuePanel;
