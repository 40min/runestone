import React, { useEffect, useRef, useState } from "react";
import {
  Box,
  Checkbox,
  CircularProgress,
  Dialog,
  IconButton,
  TextField,
  Typography,
} from "@mui/material";
import AutoFixNormalIcon from "@mui/icons-material/AutoFixNormal";
import AutoFixHighIcon from "@mui/icons-material/AutoFixHigh";
import SearchIcon from "@mui/icons-material/Search";
import CloseIcon from "@mui/icons-material/Close";
import DeleteOutlineIcon from "@mui/icons-material/DeleteOutline";
import { CustomButton, Snackbar } from "./ui";
import {
  improveVocabularyItem,
  type SavedVocabularyItem,
} from "../hooks/useVocabulary";
import { useApi } from "../utils/api";
import {
  VOCABULARY_IMPROVEMENT_MODES,
  type VocabularyImprovementMode,
} from "../constants";

interface AddEditVocabularyModalProps {
  open: boolean;
  item: SavedVocabularyItem | null;
  onClose: () => void;
  onSave: (updatedItem: Partial<SavedVocabularyItem>) => Promise<void>;
  onDelete?: () => Promise<void>;
  onLookup?: (wordPhrase: string) => Promise<SavedVocabularyItem | null>;
  onLookupFound?: (item: SavedVocabularyItem) => void;
}

const DEFAULT_PRIORITY_LEARN = 5;
const dialogBorder = "1px solid rgba(99, 114, 173, 0.5)";

const textFieldStyles = {
  "& .MuiInputLabel-root": {
    color: "#9eaccd",
    fontSize: "0.86rem",
    "&.Mui-focused": { color: "#61e99a" },
  },
  "& .MuiOutlinedInput-root": {
    color: "#f2f5ff",
    backgroundColor: "rgba(6, 12, 43, 0.62)",
    borderRadius: 1.5,
    "& fieldset": { borderColor: "rgba(103, 121, 181, 0.5)" },
    "&:hover fieldset": { borderColor: "rgba(137, 155, 211, 0.72)" },
    "&.Mui-focused fieldset": { borderColor: "#38e07b" },
  },
};

const sectionLabelStyles = {
  color: "#e9eeff",
  fontSize: "0.72rem",
  fontWeight: 700,
  letterSpacing: "0.08em",
  textTransform: "uppercase",
};

const AddEditVocabularyModal: React.FC<AddEditVocabularyModalProps> = ({
  open,
  item,
  onClose,
  onSave,
  onDelete,
  onLookup,
  onLookupFound,
}) => {
  const [wordPhrase, setWordPhrase] = useState("");
  const [translation, setTranslation] = useState("");
  const [examplePhrase, setExamplePhrase] = useState("");
  const [extraInfo, setExtraInfo] = useState("");
  const [inLearn, setInLearn] = useState(false);
  const [priorityLearn, setPriorityLearn] = useState(DEFAULT_PRIORITY_LEARN);
  const [isImproving, setIsImproving] = useState(false);
  const [isLookingUp, setIsLookingUp] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [lookupMessage, setLookupMessage] = useState<string | null>(null);
  const [lookupSeverity, setLookupSeverity] = useState<"success" | "info">("info");
  const [error, setError] = useState<string | null>(null);
  const lookupRequestIdRef = useRef(0);
  const improveRequestIdRef = useRef(0);
  const saveInFlightRef = useRef(false);
  const api = useApi();

  useEffect(() => {
    setError(null);
    setLookupMessage(null);
    if (item) {
      setWordPhrase(item.word_phrase);
      setTranslation(item.translation);
      setExamplePhrase(item.example_phrase || "");
      setExtraInfo(item.extra_info || "");
      setInLearn(item.in_learn);
      setPriorityLearn(item.priority_learn);
    } else {
      setWordPhrase("");
      setTranslation("");
      setExamplePhrase("");
      setExtraInfo("");
      setInLearn(true);
      setPriorityLearn(DEFAULT_PRIORITY_LEARN);
    }
  }, [item, open]);

  const handleClose = () => {
    lookupRequestIdRef.current += 1;
    improveRequestIdRef.current += 1;
    setIsLookingUp(false);
    setIsImproving(false);
    setLookupMessage(null);
    onClose();
  };

  const handleSave = async () => {
    if (
      !wordPhrase.trim() ||
      !translation.trim() ||
      saveInFlightRef.current
    ) {
      return;
    }

    saveInFlightRef.current = true;
    setError(null);
    setIsSaving(true);
    try {
      await onSave({
        word_phrase: wordPhrase.trim(),
        translation: translation.trim(),
        example_phrase: examplePhrase.trim() || null,
        extra_info: extraInfo.trim() || null,
        in_learn: inLearn,
        priority_learn: priorityLearn,
      });
    } catch (saveError) {
      setError(
        saveError instanceof Error
          ? saveError.message
          : "Failed to save vocabulary item"
      );
    } finally {
      saveInFlightRef.current = false;
      setIsSaving(false);
    }
  };

  const handleImproveVocabulary = async (mode: VocabularyImprovementMode) => {
    if (!wordPhrase.trim()) return;

    const requestId = improveRequestIdRef.current + 1;
    improveRequestIdRef.current = requestId;
    setError(null);
    setIsImproving(true);
    try {
      const result = await improveVocabularyItem(api, wordPhrase.trim(), mode);
      if (requestId !== improveRequestIdRef.current) return;

      if (result.translation) setTranslation(result.translation);
      if (result.example_phrase) setExamplePhrase(result.example_phrase);
      if (result.extra_info) setExtraInfo(result.extra_info);
    } catch (improveError) {
      if (requestId === improveRequestIdRef.current) {
        setError(
          improveError instanceof Error
            ? improveError.message
            : "Failed to improve vocabulary item"
        );
      }
    } finally {
      if (requestId === improveRequestIdRef.current) setIsImproving(false);
    }
  };

  const handleLookupVocabulary = async () => {
    const trimmedWordPhrase = wordPhrase.trim();
    if (!trimmedWordPhrase || !onLookup) return;

    const requestId = lookupRequestIdRef.current + 1;
    lookupRequestIdRef.current = requestId;
    setError(null);
    setIsLookingUp(true);

    try {
      const foundItem = await onLookup(trimmedWordPhrase);
      if (requestId !== lookupRequestIdRef.current) return;

      if (foundItem) {
        setLookupSeverity("success");
        setLookupMessage(
          `Found existing word: ${foundItem.word_phrase}. Editing saved entry.`
        );
        onLookupFound?.(foundItem);
      } else {
        setLookupSeverity("info");
        setLookupMessage("No existing word found.");
      }
    } catch (lookupError) {
      if (requestId === lookupRequestIdRef.current) {
        setError(
          lookupError instanceof Error
            ? lookupError.message
            : "Failed to look up vocabulary item"
        );
      }
    } finally {
      if (requestId === lookupRequestIdRef.current) setIsLookingUp(false);
    }
  };

  const fillDisabled = !wordPhrase.trim() || isImproving;

  return (
    <>
      <Dialog
        open={open}
        onClose={handleClose}
        maxWidth="lg"
        fullWidth
        aria-labelledby="edit-vocabulary-modal"
        PaperProps={{
          sx: {
            width: "min(1000px, calc(100vw - 24px))",
            maxHeight: "calc(100vh - 32px)",
            m: 1.5,
            overflow: "hidden",
            color: "#f4f7ff",
            border: dialogBorder,
            borderRadius: 2.5,
            background:
              "linear-gradient(155deg, rgba(18, 26, 65, 0.99), rgba(7, 12, 43, 0.99) 72%)",
            boxShadow: "0 32px 100px rgba(0, 0, 0, 0.58)",
          },
        }}
      >
        <Box
          component="header"
          sx={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "flex-start",
            gap: 2,
            px: { xs: 2.25, sm: 3.5 },
            py: { xs: 2, sm: 2.75 },
            borderBottom: dialogBorder,
          }}
        >
          <Box>
            <Typography
              id="edit-vocabulary-modal"
              component="h2"
              sx={{ fontSize: "1.35rem", fontWeight: 700, letterSpacing: "-0.025em" }}
            >
              {item ? "Edit vocabulary item" : "Add a vocabulary item"}
            </Typography>
            <Typography sx={{ color: "#99a8ca", fontSize: "0.78rem", mt: 0.6 }}>
              {item
                ? "Refine the meaning, study context, or learning settings."
                : "Start with the Swedish word. Runestone can help fill in the rest."}
            </Typography>
          </Box>
          <IconButton
            aria-label="Close vocabulary dialog"
            onClick={handleClose}
            sx={{ color: "#8e9bbd", border: dialogBorder, borderRadius: 1.25 }}
          >
            <CloseIcon fontSize="small" />
          </IconButton>
        </Box>

        <Box
          sx={{
            display: "grid",
            gridTemplateColumns: { xs: "1fr", md: "minmax(0, .9fr) minmax(0, 1.1fr)" },
            gap: { xs: 3.5, md: 3 },
            px: { xs: 2.25, sm: 3.5 },
            py: 3,
            overflowY: "auto",
          }}
        >
          <Box sx={{ display: "flex", flexDirection: "column", gap: 2.25 }}>
            <Box sx={{ display: "flex", alignItems: "baseline", gap: 1 }}>
              <Typography sx={sectionLabelStyles}>Core meaning</Typography>
              <Typography sx={{ color: "#7280a5", fontSize: "0.66rem" }}>Required</Typography>
            </Box>

            <Box sx={{ display: "flex", alignItems: "stretch", gap: 1 }}>
              <TextField
                label="Swedish Word/Phrase"
                value={wordPhrase}
                onChange={(event) => setWordPhrase(event.target.value)}
                fullWidth
                sx={textFieldStyles}
              />
              <CustomButton
                variant="secondary"
                title="Look up existing word"
                aria-label="Look up existing word"
                onClick={() => void handleLookupVocabulary()}
                disabled={!wordPhrase.trim() || isLookingUp || !onLookup}
                startIcon={
                  isLookingUp ? (
                    <CircularProgress size={16} color="inherit" />
                  ) : (
                    <SearchIcon fontSize="small" />
                  )
                }
                sx={{
                  flexShrink: 0,
                  color: "#dce4fa",
                  border: dialogBorder,
                  backgroundColor: "rgba(255,255,255,.02)",
                }}
              >
                Look up
              </CustomButton>
            </Box>

            <TextField
              label="English Translation"
              value={translation}
              onChange={(event) => setTranslation(event.target.value)}
              fullWidth
              sx={textFieldStyles}
            />

            <Box
              sx={{
                p: 2,
                border: dialogBorder,
                borderRadius: 2,
                backgroundColor: "rgba(255,255,255,.02)",
              }}
            >
              <Box sx={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 1 }}>
                <Box sx={{ display: "flex", alignItems: "center", gap: 1 }}>
                  <Checkbox
                    checked={inLearn}
                    onChange={(event) => setInLearn(event.target.checked)}
                    inputProps={{ "aria-label": "In Learning" }}
                    sx={{
                      p: 0.5,
                      color: "#6f7fa7",
                      "&.Mui-checked": { color: "#38e07b" },
                    }}
                  />
                  <Box>
                    <Typography sx={{ fontSize: "0.8rem", fontWeight: 700 }}>
                      Add to learning
                    </Typography>
                    <Typography sx={{ color: "#7f8db1", fontSize: "0.66rem", mt: 0.25 }}>
                      Include this word in your active study set.
                    </Typography>
                  </Box>
                </Box>
                <Box
                  sx={{
                    display: "inline-flex",
                    alignItems: "center",
                    gap: 0.65,
                    color: inLearn ? "#65eaa0" : "#98a5c4",
                    border: inLearn
                      ? "1px solid rgba(56,224,123,.28)"
                      : "1px solid rgba(148,163,184,.22)",
                    backgroundColor: inLearn
                      ? "rgba(56,224,123,.08)"
                      : "rgba(148,163,184,.06)",
                    px: 1,
                    py: 0.45,
                    borderRadius: 99,
                  }}
                >
                  <Box sx={{ width: 6, height: 6, borderRadius: "50%", bgcolor: "currentColor" }} />
                  <Typography sx={{ fontSize: "0.67rem", fontWeight: 700 }}>
                    {inLearn ? "Active" : "Skipped"}
                  </Typography>
                </Box>
              </Box>

              <Box sx={{ mt: 2 }}>
                <Box sx={{ display: "flex", justifyContent: "space-between", gap: 1, mb: 0.8 }}>
                  <Typography sx={{ color: "#8f9dc0", fontSize: "0.66rem" }}>
                    Study priority
                  </Typography>
                  <Typography sx={{ color: "#8f9dc0", fontSize: "0.66rem" }}>
                    0 = sooner · 9 = later
                  </Typography>
                </Box>
                <Box
                  role="group"
                  aria-label="Priority (0-9)"
                  sx={{ display: "grid", gridTemplateColumns: "repeat(10, 1fr)", gap: 0.45 }}
                >
                  {Array.from({ length: 10 }, (_, priority) => (
                    <Box
                      component="button"
                      type="button"
                      key={priority}
                      aria-label={`Priority ${priority}`}
                      aria-pressed={priorityLearn === priority}
                      onClick={() => setPriorityLearn(priority)}
                      sx={{
                        minWidth: 0,
                        height: 32,
                        p: 0,
                        borderRadius: 1,
                        border:
                          priorityLearn === priority ? "1px solid #38e07b" : dialogBorder,
                        color: priorityLearn === priority ? "#071b11" : "#8593b7",
                        backgroundColor:
                          priorityLearn === priority ? "#38e07b" : "rgba(255,255,255,.02)",
                        font: "inherit",
                        fontSize: "0.68rem",
                        fontWeight: priorityLearn === priority ? 700 : 400,
                        cursor: "pointer",
                      }}
                    >
                      {priority}
                    </Box>
                  ))}
                </Box>
              </Box>
            </Box>
          </Box>

          <Box sx={{ display: "flex", flexDirection: "column", gap: 2.25 }}>
            <Box sx={{ display: "flex", alignItems: "baseline", gap: 1 }}>
              <Typography sx={sectionLabelStyles}>Learning context</Typography>
              <Typography sx={{ color: "#7280a5", fontSize: "0.66rem" }}>
                Optional, but useful
              </Typography>
            </Box>

            <Box sx={{ position: "relative" }}>
              <TextField
                label="Example Phrase (Optional)"
                value={examplePhrase}
                onChange={(event) => setExamplePhrase(event.target.value)}
                fullWidth
                multiline
                minRows={4}
                sx={{ ...textFieldStyles, "& textarea": { pr: 15 } }}
              />
              <CustomButton
                variant="secondary"
                size="small"
                title="Fill Example"
                aria-label="Suggest example"
                onClick={() => void handleImproveVocabulary(VOCABULARY_IMPROVEMENT_MODES.EXAMPLE_ONLY)}
                disabled={fillDisabled}
                startIcon={<AutoFixNormalIcon sx={{ fontSize: 14 }} />}
                sx={{
                  position: "absolute",
                  top: 8,
                  right: 8,
                  color: "#65eaa0",
                  border: "1px solid rgba(56,224,123,.28)",
                  backgroundColor: "rgba(56,224,123,.06)",
                }}
              >
                Suggest example
              </CustomButton>
            </Box>

            <Box sx={{ position: "relative" }}>
              <TextField
                label="Extra Info (Optional)"
                value={extraInfo}
                onChange={(event) => setExtraInfo(event.target.value)}
                fullWidth
                multiline
                minRows={4}
                sx={{ ...textFieldStyles, "& textarea": { pr: 15 } }}
              />
              <CustomButton
                variant="secondary"
                size="small"
                title="Fill Extra Info"
                aria-label="Suggest grammar"
                onClick={() => void handleImproveVocabulary(VOCABULARY_IMPROVEMENT_MODES.EXTRA_INFO_ONLY)}
                disabled={fillDisabled}
                startIcon={<AutoFixNormalIcon sx={{ fontSize: 14 }} />}
                sx={{
                  position: "absolute",
                  top: 8,
                  right: 8,
                  color: "#65eaa0",
                  border: "1px solid rgba(56,224,123,.28)",
                  backgroundColor: "rgba(56,224,123,.06)",
                }}
              >
                Suggest grammar
              </CustomButton>
            </Box>

            {error && (
              <Typography role="alert" sx={{ color: "#fda4af", fontSize: "0.8rem" }}>
                {error}
              </Typography>
            )}
          </Box>
        </Box>

        <Box
          component="footer"
          sx={{
            display: "flex",
            alignItems: { xs: "stretch", sm: "center" },
            justifyContent: "space-between",
            flexDirection: { xs: "column", sm: "row" },
            gap: 2,
            px: { xs: 2.25, sm: 3.5 },
            py: 2,
            borderTop: dialogBorder,
            backgroundColor: "rgba(5, 10, 38, 0.52)",
          }}
        >
          <Box sx={{ display: "flex", alignItems: "center", gap: 1.25, flexWrap: "wrap" }}>
            <CustomButton
              variant="secondary"
              title="Fill All"
              aria-label="Fill with AI"
              onClick={() => void handleImproveVocabulary(VOCABULARY_IMPROVEMENT_MODES.ALL_FIELDS)}
              disabled={fillDisabled}
              startIcon={
                isImproving ? (
                  <CircularProgress size={16} color="inherit" />
                ) : (
                  <AutoFixHighIcon fontSize="small" />
                )
              }
              sx={{
                color: "#65eaa0",
                border: "1px solid rgba(56,224,123,.34)",
                backgroundColor: "rgba(56,224,123,.08)",
              }}
            >
              Fill with AI
            </CustomButton>
            <Typography sx={{ color: "#7180a7", fontSize: "0.67rem", maxWidth: 210 }}>
              Suggest translation, example, and grammar details.
            </Typography>
          </Box>

          <Box sx={{ display: "flex", justifyContent: "flex-end", alignItems: "center", gap: 1 }}>
            {item && onDelete && (
              <CustomButton
                variant="secondary"
                startIcon={<DeleteOutlineIcon fontSize="small" />}
                onClick={() => void onDelete()}
                sx={{ color: "#fda4af", mr: { xs: "auto", sm: 1 } }}
              >
                Delete
              </CustomButton>
            )}
            <CustomButton variant="secondary" onClick={handleClose}>
              Cancel
            </CustomButton>
            <CustomButton
              variant="primary"
              onClick={() => void handleSave()}
              disabled={!wordPhrase.trim() || !translation.trim() || isSaving}
            >
              {isSaving
                ? "Saving..."
                : item
                  ? "Save changes"
                  : "Add to vocabulary"}
            </CustomButton>
          </Box>
        </Box>
      </Dialog>

      <Snackbar
        open={Boolean(lookupMessage)}
        message={lookupMessage || ""}
        severity={lookupSeverity}
        autoHideDuration={3500}
        onClose={() => setLookupMessage(null)}
      />
    </>
  );
};

export default AddEditVocabularyModal;
