import React, { useState, useEffect } from "react";
import { Modal, Box, TextField, Typography, IconButton } from "@mui/material";
import AutoFixNormal from "@mui/icons-material/AutoFixNormal";
import AutoFixHigh from "@mui/icons-material/AutoFixHigh";
import { CustomButton, StyledCheckbox } from "./ui";
import { improveVocabularyItem } from "../hooks/useVocabulary";
import { VOCABULARY_IMPROVEMENT_MODES, type VocabularyImprovementMode } from "../constants";

interface SavedVocabularyItem {
  id: number;
  user_id: number;
  word_phrase: string;
  translation: string;
  example_phrase: string | null;
  extra_info: string | null;
  in_learn: boolean;
  last_learned: string | null;
  created_at: string;
}

interface AddEditVocabularyModalProps {
  open: boolean;
  item: SavedVocabularyItem | null;
  onClose: () => void;
  onSave: (updatedItem: Partial<SavedVocabularyItem>) => Promise<void>;
  onDelete?: () => Promise<void>;
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

const AddEditVocabularyModal: React.FC<AddEditVocabularyModalProps> = ({
  open,
  item,
  onClose,
  onSave,
  onDelete,
}) => {
  const [wordPhrase, setWordPhrase] = useState("");
  const [translation, setTranslation] = useState("");
  const [examplePhrase, setExamplePhrase] = useState("");
  const [extraInfo, setExtraInfo] = useState("");
  const [inLearn, setInLearn] = useState(false);
  const [isImproving, setIsImproving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setError(null);
    if (item) {
      setWordPhrase(item.word_phrase);
      setTranslation(item.translation);
      setExamplePhrase(item.example_phrase || "");
      setExtraInfo(item.extra_info || "");
      setInLearn(item.in_learn);
    } else {
      setWordPhrase("");
      setTranslation("");
      setExamplePhrase("");
      setExtraInfo("");
      setInLearn(false);
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
      });
    } catch (err) {
      const errorMessage =
        err instanceof Error ? err.message : "Failed to save vocabulary item";
      setError(errorMessage);
    }
  };

  const handleClose = () => {
    onClose();
  };

  const handleImproveVocabulary = async (mode: VocabularyImprovementMode) => {
    if (!wordPhrase.trim()) return;

    setError("");
    setIsImproving(true);
    try {
      const result = await improveVocabularyItem(wordPhrase.trim(), mode);
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

  const handleFillAll = () => handleImproveVocabulary(VOCABULARY_IMPROVEMENT_MODES.ALL_FIELDS);

  const handleFillExample = () => handleImproveVocabulary(VOCABULARY_IMPROVEMENT_MODES.EXAMPLE_ONLY);

  return (
    <Modal
      open={open}
      onClose={handleClose}
      aria-labelledby="edit-vocabulary-modal"
      aria-describedby="edit-vocabulary-modal-description"
    >
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
          <TextField
            label="Swedish Word/Phrase"
            value={wordPhrase}
            onChange={(e) => setWordPhrase(e.target.value)}
            fullWidth
            variant="outlined"
            sx={textFieldStyles}
          />

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
            <StyledCheckbox
              checked={inLearn}
              onChange={setInLearn}
              label="In Learning"
            />
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
    </Modal>
  );
};

export default AddEditVocabularyModal;
