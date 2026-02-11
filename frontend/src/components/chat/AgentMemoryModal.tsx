import React, { useState, useEffect, useCallback, useRef } from "react";
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Box,
  Typography,
  IconButton,
  Chip,
  Card,
  CardContent,
  CardActions,
  CircularProgress,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  TextField,
  Tooltip,
} from "@mui/material";
import CloseIcon from "@mui/icons-material/Close";
import AddIcon from "@mui/icons-material/Add";
import DeleteIcon from "@mui/icons-material/Delete";
import EditIcon from "@mui/icons-material/Edit";
import TrendingUpIcon from "@mui/icons-material/TrendingUp";
import PsychologyIcon from "@mui/icons-material/Psychology";
import { CustomButton, TabNavigation } from "../ui";
import useMemoryItems, { type MemoryItem, type MemoryCategory, type MemoryItemCreate } from "../../hooks/useMemoryItems";

interface AgentMemoryModalProps {
  open: boolean;
  onClose: () => void;
}

const CATEGORIES: { id: MemoryCategory; label: string }[] = [
  { id: "personal_info", label: "Personal Info" },
  { id: "area_to_improve", label: "Areas to Improve" },
  { id: "knowledge_strength", label: "Knowledge Strengths" },
];

const STATUS_OPTIONS: Record<string, { label: string; color: "default" | "primary" | "secondary" | "error" | "info" | "success" | "warning" }> = {
  // Common/Personal Info
  active: { label: "Active", color: "info" },
  outdated: { label: "Outdated", color: "default" },
  // Areas to Improve
  struggling: { label: "Struggling", color: "error" },
  improving: { label: "Improving", color: "warning" },
  mastered: { label: "Mastered", color: "success" },
  // Knowledge Strengths
  archived: { label: "Archived", color: "default" },
};

const textFieldStyles = {
  "& .MuiOutlinedInput-root": {
    color: "white",
    "& fieldset": { borderColor: "#374151" },
    "&:hover fieldset": { borderColor: "#6b7280" },
    "&.Mui-focused fieldset": { borderColor: "var(--primary-color)" },
  },
  "& .MuiInputLabel-root": {
    color: "#9ca3af",
    "&.Mui-focused": { color: "var(--primary-color)" },
  },
};

const AgentMemoryModal: React.FC<AgentMemoryModalProps> = ({ open, onClose }) => {
  const [activeTab, setActiveTab] = useState<MemoryCategory>("personal_info");
  const [statusFilter, setStatusFilter] = useState<string>("all");
  const { items, loading, error, hasMore, fetchItems, createItem, promoteItem, deleteItem, clearCategory } = useMemoryItems();

  const [isFormOpen, setIsFormOpen] = useState(false);
  const [editingItem, setEditingItem] = useState<MemoryItem | null>(null);
  const [formData, setFormData] = useState<MemoryItemCreate>({
    category: "personal_info",
    key: "",
    content: "",
    status: undefined,
  });

  const scrollContainerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (open) {
      fetchItems(activeTab, statusFilter === "all" ? undefined : statusFilter, true);
    }
  }, [open, activeTab, statusFilter, fetchItems]);

  const handleScroll = useCallback(() => {
    if (!scrollContainerRef.current || loading || !hasMore) return;

    const { scrollTop, scrollHeight, clientHeight } = scrollContainerRef.current;
    if (scrollHeight - scrollTop <= clientHeight + 100) {
      fetchItems(activeTab, statusFilter === "all" ? undefined : statusFilter, false);
    }
  }, [loading, hasMore, fetchItems, activeTab, statusFilter]);

  const handleTabChange = (tabId: string) => {
    setActiveTab(tabId as MemoryCategory);
    setStatusFilter("all");
  };

  const handleOpenForm = (item?: MemoryItem) => {
    if (item) {
      setEditingItem(item);
      setFormData({
        category: item.category,
        key: item.key,
        content: item.content,
        status: item.status,
      });
    } else {
      setEditingItem(null);
      setFormData({
        category: activeTab,
        key: "",
        content: "",
        status: undefined,
      });
    }
    setIsFormOpen(true);
  };

  const handleSaveItem = async () => {
    try {
      await createItem(formData);
      setIsFormOpen(false);
    } catch (err) {
      console.error("Failed to save memory item", err);
    }
  };

  /*
  const handleUpdateStatus = async (id: number, newStatus: string) => {
    await updateStatus(id, newStatus);
  };
  */

  const handlePromote = async (id: number) => {
    await promoteItem(id);
  };

  const handleDelete = async (id: number) => {
    if (window.confirm("Are you sure you want to delete this memory item?")) {
      await deleteItem(id);
    }
  };

  const handleClearCategory = async () => {
    if (window.confirm(`Are you sure you want to clear all items in ${activeTab.replace("_", " ")}?`)) {
      await clearCategory(activeTab);
    }
  };

  return (
    <>
      <Dialog
        open={open}
        onClose={onClose}
        maxWidth="md"
        fullWidth
        PaperProps={{
          sx: {
            bgcolor: "#111827",
            color: "white",
            border: "1px solid #374151",
            borderRadius: "0.75rem",
          },
        }}
      >
        <DialogTitle sx={{ display: "flex", justifyContent: "space-between", alignItems: "center", pb: 1 }}>
          <Box sx={{ display: "flex", alignItems: "center", gap: 1.5 }}>
            <PsychologyIcon sx={{ color: "var(--primary-color)", fontSize: "2rem" }} />
            <Box>
              <Typography variant="h6" fontWeight="bold">Student Memory</Typography>
              <Typography variant="caption" sx={{ color: "#9ca3af" }}>What the agent knows about you</Typography>
            </Box>
          </Box>
          <IconButton onClick={onClose} sx={{ color: "#9ca3af" }}>
            <CloseIcon />
          </IconButton>
        </DialogTitle>

        <Box sx={{ borderBottom: 1, borderColor: "#374151" }}>
          <TabNavigation tabs={CATEGORIES} activeTab={activeTab} onTabChange={handleTabChange} />
        </Box>

        <DialogContent sx={{ p: 0, height: "60vh", display: "flex", flexDirection: "column" }}>
          <Box sx={{ p: 2, display: "flex", gap: 2, alignItems: "center", borderBottom: "1px solid #1f2937" }}>
            <FormControl size="small" sx={{ minWidth: 150, ...textFieldStyles }}>
              <InputLabel id="status-filter-label">Status</InputLabel>
              <Select
                labelId="status-filter-label"
                value={statusFilter}
                label="Status"
                onChange={(e) => setStatusFilter(e.target.value)}
              >
                <MenuItem value="all">All statuses</MenuItem>
                {Object.entries(STATUS_OPTIONS).map(([val, info]) => (
                  <MenuItem key={val} value={val}>{info.label}</MenuItem>
                ))}
              </Select>
            </FormControl>

            <Box sx={{ flexGrow: 1 }} />

            <CustomButton variant="secondary" onClick={() => handleOpenForm()} startIcon={<AddIcon />}>
              Add Item
            </CustomButton>
            <CustomButton
              variant="secondary"
              onClick={handleClearCategory}
              disabled={items.length === 0}
              sx={{ color: "#ef4444", "&:hover": { bgcolor: "rgba(239, 68, 68, 0.1)" } }}
            >
              Clear Category
            </CustomButton>
          </Box>

          <Box
            ref={scrollContainerRef}
            onScroll={handleScroll}
            sx={{ flexGrow: 1, overflowY: "auto", p: 2, display: "flex", flexDirection: "column", gap: 2 }}
          >
            {error && (
              <Box sx={{ p: 2, bgcolor: "rgba(239, 68, 68, 0.1)", border: "1px solid #ef4444", borderRadius: 1 }}>
                <Typography color="error">{error}</Typography>
              </Box>
            )}

            {items.length === 0 && !loading && (
              <Box sx={{ py: 8, textAlign: "center", color: "#6b7280" }}>
                <Typography variant="body1">No memory items found in this category.</Typography>
                <Typography variant="body2">The agent will add information here as you chat.</Typography>
              </Box>
            )}

            <Box sx={{ display: "grid", gridTemplateColumns: { xs: "1fr", sm: "1fr 1fr" }, gap: 2 }}>
              {items.map((item) => (
                <Card
                  key={item.id}
                  sx={{
                    bgcolor: "#1f2937",
                    color: "white",
                    border: "1px solid #374151",
                    "&:hover": { borderColor: "#4b5563" }
                  }}
                >
                  <CardContent sx={{ pb: 1 }}>
                    <Box sx={{ display: "flex", justifyContent: "space-between", mb: 1 }}>
                      <Typography variant="subtitle2" fontWeight="bold" sx={{ color: "var(--primary-color)" }}>
                        {item.key}
                      </Typography>
                      <Chip
                        label={STATUS_OPTIONS[item.status]?.label || item.status}
                        size="small"
                        color={STATUS_OPTIONS[item.status]?.color || "default"}
                        sx={{ height: 20, fontSize: "0.7rem", fontWeight: "bold" }}
                      />
                    </Box>
                    <Typography variant="body2" sx={{ mb: 2, whiteSpace: "pre-wrap" }}>
                      {item.content}
                    </Typography>
                    <Typography variant="caption" sx={{ color: "#6b7280" }}>
                      Updated: {new Date(item.updated_at).toLocaleDateString()}
                    </Typography>
                  </CardContent>
                  <CardActions sx={{ justifyContent: "flex-end", pt: 0 }}>
                    {item.category === "area_to_improve" && item.status === "mastered" && (
                      <Tooltip title="Promote to Strength">
                        <IconButton size="small" onClick={() => handlePromote(item.id)} sx={{ color: "var(--primary-color)" }}>
                          <TrendingUpIcon fontSize="small" />
                        </IconButton>
                      </Tooltip>
                    )}
                    <IconButton size="small" onClick={() => handleOpenForm(item)} sx={{ color: "#9ca3af" }}>
                      <EditIcon fontSize="small" />
                    </IconButton>
                    <IconButton size="small" onClick={() => handleDelete(item.id)} sx={{ color: "#ef4444" }}>
                      <DeleteIcon fontSize="small" />
                    </IconButton>
                  </CardActions>
                </Card>
              ))}
            </Box>

            {loading && (
              <Box sx={{ display: "flex", justifyContent: "center", py: 2 }}>
                <CircularProgress size={24} />
              </Box>
            )}
          </Box>
        </DialogContent>
      </Dialog>

      {/* Item Form Dialog */}
      <Dialog
        open={isFormOpen}
        onClose={() => setIsFormOpen(false)}
        PaperProps={{
          sx: {
            bgcolor: "#1f2937",
            color: "white",
            border: "1px solid #374151",
            borderRadius: "0.5rem",
          }
        }}
      >
        <DialogTitle>{editingItem ? "Edit Memory Item" : "Add Memory Item"}</DialogTitle>
        <DialogContent sx={{ display: "flex", flexDirection: "column", gap: 3, pt: 2, minWidth: 400 }}>
          <TextField
            label="Key"
            value={formData.key}
            onChange={(e) => setFormData({ ...formData, key: e.target.value })}
            fullWidth
            required
            placeholder="e.g. topic-name, interest-label"
            sx={textFieldStyles}
          />
          <TextField
            label="Content"
            value={formData.content}
            onChange={(e) => setFormData({ ...formData, content: e.target.value })}
            fullWidth
            required
            multiline
            rows={3}
            placeholder="Describe what the agent should remember..."
            sx={textFieldStyles}
          />
          <FormControl fullWidth sx={textFieldStyles}>
            <InputLabel id="form-status-label">Status</InputLabel>
            <Select
              labelId="form-status-label"
              value={formData.status ?? ""}
              label="Status"
              onChange={(e) =>
                setFormData({
                  ...formData,
                  status: e.target.value ? String(e.target.value) : undefined,
                })
              }
            >
              <MenuItem value="">Default</MenuItem>
              {Object.entries(STATUS_OPTIONS).map(([val, info]) => (
                <MenuItem key={val} value={val}>{info.label}</MenuItem>
              ))}
            </Select>
          </FormControl>
        </DialogContent>
        <DialogActions sx={{ p: 3 }}>
          <CustomButton variant="secondary" onClick={() => setIsFormOpen(false)}>Cancel</CustomButton>
          <CustomButton
            variant="save"
            onClick={handleSaveItem}
            disabled={!formData.key.trim() || !formData.content.trim()}
          >
            Save
          </CustomButton>
        </DialogActions>
      </Dialog>
    </>
  );
};

export default AgentMemoryModal;
