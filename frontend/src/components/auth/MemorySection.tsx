
import React, { useState } from "react";
import {
  Box,
  Typography,
  Paper,
  Accordion,
  AccordionSummary,
  AccordionDetails,
  Button,
  IconButton,
  TextField,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Alert,
  CircularProgress,
} from "@mui/material";
import ExpandMoreIcon from "@mui/icons-material/ExpandMore";
import DeleteIcon from "@mui/icons-material/Delete";
import EditIcon from "@mui/icons-material/Edit";
import SaveIcon from "@mui/icons-material/Save";
import CloseIcon from "@mui/icons-material/Close";
import type { UserData } from "../../types/auth";
import { useAuthActions } from "../../hooks/useAuth";

interface MemorySectionProps {
  userData: UserData;
}

interface MemoryFieldProps {
  label: string;
  category: "personal_info" | "areas_to_improve" | "knowledge_strengths";
  data: Record<string, unknown> | null | undefined;
  onClear: (category: string) => void;
  onSave: (category: string, newData: Record<string, unknown>) => Promise<void>;
  loading: boolean;
}

const MemoryField: React.FC<MemoryFieldProps> = ({
  label,
  category,
  data,
  onClear,
  onSave,
  loading,
}) => {
  const [isEditing, setIsEditing] = useState(false);
  const [editValue, setEditValue] = useState("");
  const [error, setError] = useState<string | null>(null);

  const handleEdit = () => {
    setEditValue(JSON.stringify(data || {}, null, 2));
    setIsEditing(true);
    setError(null);
  };

  const handleCancel = () => {
    setIsEditing(false);
    setError(null);
  };

  const handleSave = async () => {
    try {
      const parsed = JSON.parse(editValue);
      await onSave(category, parsed);
      setError(null);
    } catch {
      setError("Invalid JSON format");
    }
  };

  return (
    <Box sx={{ mb: 3 }}>
      <Box sx={{ display: "flex", alignItems: "center", mb: 1 }}>
        <Typography variant="subtitle1" fontWeight="bold" sx={{ flexGrow: 1 }}>
          {label}
        </Typography>
        {isEditing ? (
          <>
            <IconButton onClick={handleSave} disabled={loading} color="primary">
              <SaveIcon />
            </IconButton>
            <IconButton onClick={handleCancel} disabled={loading}>
              <CloseIcon />
            </IconButton>
          </>
        ) : (
          <>
            <IconButton onClick={handleEdit} disabled={loading}>
              <EditIcon />
            </IconButton>
            <IconButton
              onClick={() => onClear(category)}
              disabled={loading || !data}
              color="error"
            >
              <DeleteIcon />
            </IconButton>
          </>
        )}
      </Box>

      {error && (
        <Alert severity="error" sx={{ mb: 1 }}>
          {error}
        </Alert>
      )}

      {isEditing ? (
        <TextField
          fullWidth
          multiline
          minRows={3}
          value={editValue}
          onChange={(e) => setEditValue(e.target.value)}
          disabled={loading}
          sx={{ fontFamily: "monospace" }}
        />
      ) : (
        <Paper
          variant="outlined"
          sx={{ p: 2, bgcolor: "background.default", minHeight: "80px" }}
        >
          {data && Object.keys(data).length > 0 ? (
            <pre style={{ margin: 0, whiteSpace: "pre-wrap", fontSize: "0.875rem" }}>
              {JSON.stringify(data, null, 2)}
            </pre>
          ) : (
            <Typography variant="body2" color="text.secondary" fontStyle="italic">
              No memory stored for this category yet.
            </Typography>
          )}
        </Paper>
      )}
    </Box>
  );
};

export const MemorySection: React.FC<MemorySectionProps> = ({ userData }) => {
  const { clearMemory, updateProfile, loading } = useAuthActions();
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [clearTarget, setClearTarget] = useState<string | null>(null);

  const handleClear = (category?: string) => {
    setClearTarget(category || null);
    setConfirmOpen(true);
  };

  const confirmClear = async () => {
    if (clearTarget) {
      await clearMemory(clearTarget);
    } else {
      await clearMemory();
    }
    setConfirmOpen(false);
    setClearTarget(null);
  };

  const handleSave = async (category: string, newData: Record<string, unknown>) => {
    await updateProfile({ [category]: newData });
  };

  return (
    <Accordion defaultExpanded>
      <AccordionSummary expandIcon={<ExpandMoreIcon />}>
        <Typography variant="h6">Björn's Memory</Typography>
      </AccordionSummary>
      <AccordionDetails>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
          This is what the AI agent remembers about you to personalize your learning.
          You can edit or clear this information at any time.
        </Typography>

        <MemoryField
          label="Personal Info"
          category="personal_info"
          data={userData.personal_info}
          onClear={handleClear}
          onSave={handleSave}
          loading={loading}
        />

        <MemoryField
          label="Areas to Improve"
          category="areas_to_improve"
          data={userData.areas_to_improve}
          onClear={handleClear}
          onSave={handleSave}
          loading={loading}
        />

        <MemoryField
          label="Knowledge Strengths"
          category="knowledge_strengths"
          data={userData.knowledge_strengths}
          onClear={handleClear}
          onSave={handleSave}
          loading={loading}
        />

        <Box sx={{ mt: 3, display: "flex", justifyContent: "flex-end" }}>
          <Button
            variant="outlined"
            color="error"
            startIcon={<DeleteIcon />}
            onClick={() => handleClear()}
            disabled={loading}
          >
            Clear All Memory
          </Button>
        </Box>

        <Dialog open={confirmOpen} onClose={() => setConfirmOpen(false)}>
          <DialogTitle>Confirm Clear Memory</DialogTitle>
          <DialogContent>
            <Typography>
              Are you sure you want to clear {clearTarget ? `the ${clearTarget.replace(/_/g, " ")}` : "ALL"} memory?
              This action cannot be undone.
            </Typography>
          </DialogContent>
          <DialogActions>
            <Button onClick={() => setConfirmOpen(false)}>Cancel</Button>
            <Button
              onClick={confirmClear}
              color="error"
              autoFocus
              disabled={loading}
            >
              {loading ? <CircularProgress size={24} /> : "Clear"}
            </Button>
          </DialogActions>
        </Dialog>
      </AccordionDetails>
    </Accordion>
  );
};
