import React, { useState, useEffect, useRef } from "react";
import {
  Modal,
  Box,
  TextField,
  Typography,
  IconButton,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  CircularProgress,
} from "@mui/material";
import AutoFixNormal from "@mui/icons-material/AutoFixNormal";
import AutoFixHigh from "@mui/icons-material/AutoFixHigh";
import Search from "@mui/icons-material/Search";
import { CustomButton, StyledCheckbox, Snackbar } from "./ui";
import {
  improveVocabularyItem,
  type SavedVocabularyItem,
} from "../hooks/useVocabulary";
import { useApi } from "../utils/api";
import { VOCABULARY_IMPROVEMENT_MODES, type VocabularyImprovementMode } from "../constants";


interface AddEditVocabularyModalProps {
  open: boolean;
  item: SavedVocabularyItem | null;
  onClose: () => void;
  onSave: (updatedItem: Partial<SavedVocabularyItem>) => Promise<void>;
  onDelete?: () => Promise<void>;
  onLookup?: (wordPhrase: string) => Promise<SavedVocabularyItem | null>;
  onLookupFound?: (item: SavedVocabularyItem) => void;
}

const textFieldStyles = {
  "& .MuiOutlinedInput-root": {
    color: "white",
    "& fieldset": {
      borderColor: "#374151",
    },
    "&:hover fieldset": {
      borderColor: "#6b7280",
    },
    "&.Mui-focused fieldset": {
      borderColor: "var(--primary-color)",
    },
  },
  "& .MuiInputLabel-root": {
    color: "#9ca3af",
    "&.Mui-focused": {
      color: "var(--primary-color)",
    },
  },
};

const DEFAULT_PRIORITY_LEARN = 5;

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
  const [lookupMessage, setLookupMessage] = useState<string | null>(null);
  const [lookupSeverity, setLookupSeverity] = useState<"success" | "info">(
    "info"
  );
  const lookupRequestIdRef = useRef(0);
  const [error, setError] = useState<string | null>(null);

  // Get authenticated API client
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

  const handleSave = async () => {
    if (!wordPhrase.trim() || !translation.trim()) {
      return; // Basic validation
    }

    try {
      await onSave({
        word_phrase: wordPhrase.trim(),
        translation: translation.trim(),
        example_phrase: examplePhrase.trim() || null,
        extra_info: extraInfo.trim() || null,
        in_learn: inLearn,
        priority_learn: priorityLearn,
      });
    } catch (err) {
      const errorMessage =
        err instanceof Error ? err.message : "Failed to save vocabulary item";
      setError(errorMessage);
    }
  };

  const handleClose = () => {
    lookupRequestIdRef.current += 1;
    setIsLookingUp(false);
    setLookupMessage(null);
    onClose();
  };

  const handleImproveVocabulary = async (mode: VocabularyImprovementMode) => {
    if (!wordPhrase.trim()) return;

    setError("");
    setIsImproving(true);
    try {
      const result = await improveVocabularyItem(api, wordPhrase.trim(), mode);
      if (result.translation) {
        setTranslation(result.translation);
      }
      if (result.example_phrase) {
        setExamplePhrase(result.example_phrase);
      }
      if (result.extra_info) {
        setExtraInfo(result.extra_info);
      }
    } catch (err) {
      const errorMessage =
        err instanceof Error
          ? err.message
          : "Failed to improve vocabulary item";
      setError(errorMessage);
    } finally {
      setIsImproving(false);
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
    } catch (err) {
      const errorMessage =
        err instanceof Error
          ? err.message
          : "Failed to look up vocabulary item";
      if (requestId === lookupRequestIdRef.current) {
        setError(errorMessage);
      }
    } finally {
      if (requestId === lookupRequestIdRef.current) {
        setIsLookingUp(false);
      }
    }
  };

  const handleFillAll = () => handleImproveVocabulary(VOCABULARY_IMPROVEMENT_MODES.ALL_FIELDS);

  const handleFillExample = () => handleImproveVocabulary(VOCABULARY_IMPROVEMENT_MODES.EXAMPLE_ONLY);

  return (
    <Modal
      open={open}
      onClose={handleClose}
      aria-labelledby="edit-vocabulary-modal"
      aria-describedby="edit-vocabulary-modal-description"
    >
      <div>
        <Box
        sx={{
          position: "absolute",
          top: "50%",
          left: "50%",
          transform: "translate(-50%, -50%)",
          width: { xs: "90%", sm: 500 },
          bgcolor: "#1f2937",
          border: "1px solid #374151",
          borderRadius: "0.5rem",
          boxShadow: 24,
          p: 4,
          color: "white",
        }}
      >
        <Box
          sx={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            mb: 3,
          }}
        >
          <Typography variant="h6" component="h2">
            {item ? "Edit Vocabulary Item" : "Add Vocabulary Item"}
          </Typography>
          <IconButton
            onClick={handleClose}
            sx={{ color: "#9ca3af", fontSize: "1.5rem" }}
          >
            ×
          </IconButton>
        </Box>

        <Box sx={{ display: "flex", flexDirection: "column", gap: 3 }}>
          <Box sx={{ position: "relative" }}>
            <TextField
              label="Swedish Word/Phrase"
              value={wordPhrase}
              onChange={(e) => setWordPhrase(e.target.value)}
              fullWidth
              variant="outlined"
              sx={{
                ...textFieldStyles,
                "& .MuiOutlinedInput-input": {
                  pr: 5,
                },
              }}
            />
            <IconButton
              aria-label="Look up vocabulary word"
              onClick={handleLookupVocabulary}
              disabled={!wordPhrase.trim() || isLookingUp || !onLookup}
              sx={{
                position: "absolute",
                top: 8,
                right: 8,
                color: "var(--primary-color)",
                "&:hover": {
                  backgroundColor: "rgba(59, 130, 246, 0.1)",
                },
                "&:disabled": {
                  color: "#6b7280",
                },
              }}
              title="Look up existing word"
            >
              {isLookingUp ? (
                <CircularProgress size={20} color="inherit" />
              ) : (
                <Search />
              )}
            </IconButton>
          </Box>

          <TextField
            label="English Translation"
            value={translation}
            onChange={(e) => setTranslation(e.target.value)}
            fullWidth
            variant="outlined"
            sx={textFieldStyles}
          />

          <Box sx={{ position: "relative" }}>
            <TextField
              label="Example Phrase (Optional)"
              value={examplePhrase}
              onChange={(e) => setExamplePhrase(e.target.value)}
              fullWidth
              variant="outlined"
              multiline
              rows={2}
              sx={textFieldStyles}
            />
            <IconButton
              onClick={handleFillExample}
              disabled={!wordPhrase.trim() || isImproving}
              sx={{
                position: "absolute",
                top: 8,
                right: 8,
                fontSize: "0.75em",
                color: "var(--primary-color)",
                "&:hover": {
                  backgroundColor: "rgba(59, 130, 246, 0.1)",
                },
                "&:disabled": {
                  color: "#6b7280",
                },
              }}
              title="Fill Example"
            >
              <AutoFixNormal />
            </IconButton>
          </Box>

          <Box sx={{ position: "relative" }}>
            <TextField
              label="Extra Info (Optional)"
              value={extraInfo}
              onChange={(e) => setExtraInfo(e.target.value)}
              fullWidth
              variant="outlined"
              multiline
              rows={2}
              sx={textFieldStyles}
            />
            <IconButton
              onClick={() => handleImproveVocabulary(VOCABULARY_IMPROVEMENT_MODES.EXTRA_INFO_ONLY)}
              disabled={!wordPhrase.trim() || isImproving}
              sx={{
                position: "absolute",
                top: 8,
                right: 8,
                fontSize: "0.75em",
                color: "var(--primary-color)",
                "&:hover": {
                  backgroundColor: "rgba(59, 130, 246, 0.1)",
                },
                "&:disabled": {
                  color: "#6b7280",
                },
              }}
              title="Fill Extra Info"
            >
              <AutoFixNormal />
            </IconButton>
          </Box>

          <Box sx={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
            <Box sx={{ display: "flex", flexDirection: "column", gap: 1 }}>
              <StyledCheckbox
                checked={inLearn}
                onChange={setInLearn}
                label="In Learning"
              />
              <FormControl size="small" sx={{ minWidth: 220 }}>
                <InputLabel id="priority-learn-select-label" sx={{ color: "#9ca3af" }}>
                  Priority (0-9)
                </InputLabel>
                <Select
                  labelId="priority-learn-select-label"
                  id="priority-learn-select"
                  value={priorityLearn}
                  label="Priority (0-9)"
                  onChange={(event) => setPriorityLearn(Number(event.target.value))}
                  sx={{
                    color: "white",
                    "& .MuiOutlinedInput-notchedOutline": {
                      borderColor: "#374151",
                    },
                    "&:hover .MuiOutlinedInput-notchedOutline": {
                      borderColor: "#6b7280",
                    },
                    "&.Mui-focused .MuiOutlinedInput-notchedOutline": {
                      borderColor: "var(--primary-color)",
                    },
                    "& .MuiSvgIcon-root": {
                      color: "#9ca3af",
                    },
                  }}
                >
                  {Array.from({ length: 10 }, (_, priority) => (
                    <MenuItem key={priority} value={priority}>
                      {priority}
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>
              <Typography sx={{ color: "#9ca3af", fontSize: "0.75rem" }}>
                0 = highest, 9 = lowest (new words default to 5)
              </Typography>
            </Box>
            <IconButton
              onClick={handleFillAll}
              disabled={!wordPhrase.trim() || isImproving}
              sx={{
                color: "var(--primary-color)",
                "&:hover": {
                  backgroundColor: "rgba(59, 130, 246, 0.1)",
                },
                "&:disabled": {
                  color: "#6b7280",
                },
              }}
              title="Fill All"
            >
              <AutoFixHigh />
            </IconButton>
          </Box>

          {error && (
            <Typography sx={{ color: "#ef4444", fontSize: "0.875rem", mt: 1 }}>
              {error}
            </Typography>
          )}

          <Box
            sx={{
              display: "flex",
              gap: 2,
              justifyContent: "space-between",
              mt: 2,
            }}
          >
            {item && onDelete && (
              <CustomButton
                variant="secondary"
                onClick={onDelete}
                sx={{
                  color: "#ef4444",
                  "&:hover": {
                    color: "#dc2626",
                    backgroundColor: "rgba(239, 68, 68, 0.1)",
                  },
                }}
              >
                Delete
              </CustomButton>
            )}
            <Box sx={{ display: "flex", gap: 2 }}>
              <CustomButton variant="secondary" onClick={handleClose}>
                Cancel
              </CustomButton>
              <CustomButton
                variant="save"
                onClick={handleSave}
                disabled={!wordPhrase.trim() || !translation.trim()}
              >
                {item ? "Save Changes" : "Add Item"}
              </CustomButton>
            </Box>
          </Box>
        </Box>
      </Box>
        <Snackbar
          open={Boolean(lookupMessage)}
          message={lookupMessage || ""}
          severity={lookupSeverity}
          autoHideDuration={3500}
          onClose={() => setLookupMessage(null)}
        />
      </div>
    </Modal>
  );
};

export default AddEditVocabularyModal;
