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
  Divider,
} from "@mui/material";
import CloseIcon from "@mui/icons-material/Close";
import AddIcon from "@mui/icons-material/Add";
import DeleteIcon from "@mui/icons-material/Delete";
import EditIcon from "@mui/icons-material/Edit";
import CheckIcon from "@mui/icons-material/Check";
import TrendingUpIcon from "@mui/icons-material/TrendingUp";
import PsychologyIcon from "@mui/icons-material/Psychology";
import ContentCopyIcon from "@mui/icons-material/ContentCopy";
import CalendarTodayOutlinedIcon from "@mui/icons-material/CalendarTodayOutlined";
import LightbulbOutlinedIcon from "@mui/icons-material/LightbulbOutlined";
import { CustomButton, TabNavigation } from "../ui";
import useMemoryItems, {
  type MemoryItem,
  type MemoryCategory,
  type MemoryItemCreate,
  type MemorySortBy,
  type SortDirection,
} from "../../hooks/useMemoryItems";

interface AgentMemoryModalProps {
  open: boolean;
  onClose: () => void;
}

const CATEGORIES: { id: MemoryCategory; label: string }[] = [
  { id: "personal_info", label: "Personal Info" },
  { id: "area_to_improve", label: "Areas to Improve" },
  { id: "knowledge_strength", label: "Knowledge Strengths" },
];

const STATUS_OPTIONS: Record<
  string,
  {
    label: string;
    color:
      | "default"
      | "primary"
      | "secondary"
      | "error"
      | "info"
      | "success"
      | "warning";
  }
> = {
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

const STATUS_VALUES_BY_CATEGORY: Record<MemoryCategory, string[]> = {
  personal_info: ["active", "outdated"],
  area_to_improve: ["struggling", "improving", "mastered"],
  knowledge_strength: ["active", "archived"],
};

const PRIORITY_OPTIONS = [
  { value: "", label: "P9 (default lowest)" },
  { value: "0", label: "P0 (highest)" },
  { value: "1", label: "P1" },
  { value: "2", label: "P2" },
  { value: "3", label: "P3" },
  { value: "4", label: "P4" },
  { value: "5", label: "P5" },
  { value: "6", label: "P6" },
  { value: "7", label: "P7" },
  { value: "8", label: "P8" },
  { value: "9", label: "P9 (lowest)" },
];

const getPriorityChipStyles = (priority: number | null | undefined) => {
  if (priority == null) {
    return { bgcolor: "rgba(55,65,81,0.4)", color: "#6b7280" };
  }
  if (priority <= 2) {
    return { bgcolor: "rgba(239,68,68,0.2)", color: "#ef4444" };
  }
  if (priority <= 5) {
    return { bgcolor: "rgba(245,158,11,0.2)", color: "#f59e0b" };
  }
  return { bgcolor: "rgba(107,114,128,0.2)", color: "#9ca3af" };
};

const getStatusChipStyles = (status: string) => {
  switch (status) {
    case "struggling":
      return {
        bgcolor: "rgba(239, 68, 68, 0.16)",
        color: "#ff8a80",
        border: "1px solid rgba(239, 68, 68, 0.18)",
      };
    case "improving":
      return {
        bgcolor: "rgba(245, 158, 11, 0.14)",
        color: "#fbbf24",
        border: "1px solid rgba(245, 158, 11, 0.18)",
      };
    case "mastered":
    case "active":
      return {
        bgcolor: "rgba(56, 224, 123, 0.14)",
        color: "#7df0aa",
        border: "1px solid rgba(56, 224, 123, 0.18)",
      };
    default:
      return {
        bgcolor: "rgba(148, 163, 184, 0.12)",
        color: "#cbd5e1",
        border: "1px solid rgba(148, 163, 184, 0.16)",
      };
  }
};

const CATEGORY_HELP_TEXT: Record<MemoryCategory, string> = {
  personal_info:
    "These are the personal details your teacher uses to keep guidance relevant and consistent.",
  area_to_improve:
    "These are areas where you've shown difficulty. Focus on them to improve faster!",
  knowledge_strength:
    "These are the concepts you're handling well. Lean on them when building confidence in new topics.",
};

const MEMORY_DATE_LOCALE = "en-GB";

const textFieldStyles = {
  "& .MuiOutlinedInput-root": {
    color: "white",
    "& fieldset": { borderColor: "rgba(148, 163, 184, 0.2)" },
    "&:hover fieldset": { borderColor: "rgba(148, 163, 184, 0.4)" },
    "&.Mui-focused fieldset": { borderColor: "var(--primary-color)" },
    bgcolor: "rgba(15, 23, 42, 0.55)",
    backdropFilter: "blur(10px)",
  },
  "& .MuiInputLabel-root": {
    color: "#9ca3af",
    "&.Mui-focused": { color: "var(--primary-color)" },
  },
  "& .MuiSelect-icon": {
    color: "#94a3b8",
  },
};

const AgentMemoryModal: React.FC<AgentMemoryModalProps> = ({
  open,
  onClose,
}) => {
  const [activeTab, setActiveTab] = useState<MemoryCategory>("personal_info");
  const [statusFilter, setStatusFilter] = useState<string>("all");
  const [sortBy, setSortBy] = useState<MemorySortBy>("updated_at");
  const [sortDirection, setSortDirection] = useState<SortDirection>("desc");
  const {
    items,
    loading,
    error,
    hasMore,
    fetchItems,
    createItem,
    updatePriority,
    promoteItem,
    deleteItem,
    clearCategory,
  } = useMemoryItems();

  const [isFormOpen, setIsFormOpen] = useState(false);
  const [editingItem, setEditingItem] = useState<MemoryItem | null>(null);
  const [confirmDeleteId, setConfirmDeleteId] = useState<number | null>(null);
  const [confirmClear, setConfirmClear] = useState(false);
  const [editingPriorityId, setEditingPriorityId] = useState<number | null>(null);
  const [formData, setFormData] = useState<MemoryItemCreate>({
    category: "personal_info",
    key: "",
    content: "",
    status: undefined,
    priority: null,
  });

  const scrollContainerRef = useRef<HTMLDivElement>(null);
  const displayedCountLabel = `${items.length} item${items.length === 1 ? "" : "s"}`;

  const getItemTitle = (item: MemoryItem): string => {
    if (!item.metadata_json) return item.key;
    try {
      const meta = JSON.parse(item.metadata_json) as { title?: unknown };
      if (typeof meta?.title === "string" && meta.title.trim()) {
        return meta.title.trim();
      }
    } catch {
      // ignore invalid metadata_json
    }
    return item.key;
  };

  const copyKeyToClipboard = async (key: string) => {
    try {
      await navigator.clipboard.writeText(key);
    } catch (err) {
      console.error("Failed to copy key", err);
    }
  };

  useEffect(() => {
    if (open) {
      fetchItems(
        activeTab,
        statusFilter === "all" ? undefined : statusFilter,
        true,
        sortBy,
        sortDirection,
      );
    }
  }, [open, activeTab, statusFilter, sortBy, sortDirection, fetchItems]);

  useEffect(() => {
    if (!open) {
      setConfirmDeleteId(null);
      setConfirmClear(false);
      setEditingPriorityId(null);
    }
  }, [open]);

  const handleScroll = useCallback(() => {
    if (!scrollContainerRef.current || loading || !hasMore) return;

    const { scrollTop, scrollHeight, clientHeight } =
      scrollContainerRef.current;
    if (scrollHeight - scrollTop <= clientHeight + 100) {
      fetchItems(
        activeTab,
        statusFilter === "all" ? undefined : statusFilter,
        false,
        sortBy,
        sortDirection,
      );
    }
  }, [loading, hasMore, fetchItems, activeTab, statusFilter, sortBy, sortDirection]);

  const handleTabChange = (tabId: string) => {
    setActiveTab(tabId as MemoryCategory);
    setStatusFilter("all");
    setSortBy("updated_at");
    setSortDirection("desc");
    setConfirmDeleteId(null);
    setConfirmClear(false);
    setEditingPriorityId(null);
  };

  const handleOpenForm = (item?: MemoryItem) => {
    if (item) {
      setEditingItem(item);
      setFormData({
        category: item.category,
        key: item.key,
        content: item.content,
        status: item.status,
        priority: item.priority,
      });
    } else {
      setEditingItem(null);
      setFormData({
        category: activeTab,
        key: "",
        content: "",
        status: undefined,
        priority: null,
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

  const handlePromote = async (id: number) => {
    await promoteItem(
      id,
      activeTab,
      statusFilter === "all" ? undefined : statusFilter,
      sortBy,
      sortDirection,
    );
  };

  const handleDelete = async (id: number) => {
    setConfirmDeleteId(id);
  };

  const handleClearCategory = async () => {
    setConfirmClear(true);
  };

  const handlePriorityChange = async (id: number, value: string) => {
    const priority = value === "" ? null : Number(value);
    setEditingPriorityId(null);
    await updatePriority(id, priority);
  };

  const renderStatusMenuItems = (category: MemoryCategory) =>
    STATUS_VALUES_BY_CATEGORY[category].map((val) => {
      const info = STATUS_OPTIONS[val];
      return (
        <MenuItem key={val} value={val}>
          {info?.label ?? val}
        </MenuItem>
      );
    });

  return (
    <>
      <Dialog
        open={open}
        onClose={onClose}
        fullWidth
        maxWidth={false}
        sx={{
          "& .MuiBackdrop-root": {
            bgcolor: "rgba(2, 6, 23, 0.78)",
            backdropFilter: "blur(10px)",
          },
        }}
        PaperProps={{
          sx: {
            width: { xs: "calc(100vw - 16px)", sm: "calc(100vw - 48px)", lg: "1220px" },
            maxWidth: "1220px",
            maxHeight: { xs: "calc(100vh - 16px)", sm: "calc(100vh - 40px)" },
            bgcolor: "rgba(15, 23, 42, 0.96)",
            backgroundImage:
              "radial-gradient(circle at top left, rgba(56, 224, 123, 0.08), transparent 32%), linear-gradient(180deg, rgba(15,23,42,0.98) 0%, rgba(15,23,42,0.94) 100%)",
            color: "white",
            border: "1px solid rgba(148, 163, 184, 0.18)",
            borderRadius: { xs: "1rem", md: "1.25rem" },
            boxShadow: "0 28px 80px rgba(2, 6, 23, 0.6)",
            overflow: "hidden",
          },
        }}
      >
        <DialogTitle
          sx={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            px: { xs: 2.25, md: 4.5 },
            pt: { xs: 2.25, md: 4 },
            pb: { xs: 2, md: 2.5 },
          }}
        >
          <Box sx={{ display: "flex", alignItems: "center", gap: { xs: 1.5, md: 2 } }}>
            <PsychologyIcon
              sx={{ color: "var(--primary-color)", fontSize: { xs: "2.6rem", md: "3.2rem" } }}
            />
            <Box>
              <Typography
                variant="h6"
                fontWeight="bold"
                sx={{ fontSize: { xs: "1.7rem", md: "2.1rem" }, lineHeight: 1.1, mb: 0.5 }}
              >
                Teacher&apos;s Memory
              </Typography>
              <Typography
                variant="body2"
                sx={{ color: "#a5b4c7", fontSize: { xs: "0.95rem", md: "1rem" } }}
              >
                What your teacher remembers about your learning journey
              </Typography>
            </Box>
          </Box>
          <IconButton
            onClick={onClose}
            sx={{
              color: "#94a3b8",
              mt: { xs: -0.5, md: -1 },
              mr: { xs: -0.5, md: -1 },
              "&:hover": { bgcolor: "rgba(148, 163, 184, 0.08)", color: "white" },
            }}
          >
            <CloseIcon />
          </IconButton>
        </DialogTitle>

        <TabNavigation
          tabs={CATEGORIES}
          activeTab={activeTab}
          onTabChange={handleTabChange}
          containerSx={{
            px: { xs: 2.25, md: 4.5 },
            borderColor: "rgba(148, 163, 184, 0.18)",
          }}
          tabsSx={{
            display: "grid",
            gridTemplateColumns: `repeat(${CATEGORIES.length}, minmax(0, 1fr))`,
            gap: { xs: 0.5, md: 1.5 },
            alignItems: "stretch",
          }}
          buttonSx={{
            px: { xs: 0.5, md: 0 },
            py: 1.6,
            color: "#d5dbe6",
            fontSize: { xs: "0.95rem", md: "1.02rem" },
            fontWeight: 500,
            whiteSpace: "normal",
            textAlign: "center",
            lineHeight: 1.35,
            minWidth: 0,
            "&:hover": {
              color: "white",
            },
          }}
          activeButtonSx={{
            color: "var(--primary-color)",
            fontWeight: 700,
            "&:hover": {
              color: "var(--primary-color)",
            },
          }}
        />

        <DialogContent
          sx={{
            px: { xs: 2.25, md: 4.5 },
            pt: { xs: 2.25, md: 2.5 },
            pb: { xs: 2.25, md: 3 },
            height: { xs: "auto", md: "68vh" },
            minHeight: 0,
            display: "flex",
            flexDirection: "column",
          }}
        >
          <Box
            sx={{
              p: { xs: 1.5, sm: 2, md: 2.25 },
              display: "flex",
              flexWrap: "wrap",
              gap: { xs: 1.25, md: 1.5 },
              alignItems: { xs: "stretch", md: "flex-end" },
              border: "1px solid rgba(148, 163, 184, 0.18)",
              borderRadius: "1rem",
              bgcolor: "rgba(30, 41, 59, 0.56)",
              boxShadow: "inset 0 1px 0 rgba(255,255,255,0.03)",
              mb: 2,
            }}
          >
            <Box
              sx={{
                display: "grid",
                gridTemplateColumns: { xs: "1fr", sm: "repeat(2, minmax(0, 1fr))", lg: "repeat(3, minmax(0, 1fr))" },
                gap: { xs: 1.25, md: 1.5 },
                flex: "1 1 560px",
                minWidth: 0,
              }}
            >
              <FormControl size="small" sx={{ minWidth: 0, ...textFieldStyles }}>
                <Typography
                  id="status-filter-label"
                  component="label"
                  sx={{ mb: 0.75, color: "#cbd5e1", fontSize: "0.92rem", fontWeight: 500 }}
                >
                  Status
                </Typography>
                <Select
                  labelId="status-filter-label"
                  value={statusFilter}
                  onChange={(e) => setStatusFilter(e.target.value)}
                >
                  <MenuItem value="all">All statuses</MenuItem>
                  {renderStatusMenuItems(activeTab)}
                </Select>
              </FormControl>

              <FormControl size="small" sx={{ minWidth: 0, ...textFieldStyles }}>
                <Typography
                  id="sort-by-label"
                  component="label"
                  sx={{ mb: 0.75, color: "#cbd5e1", fontSize: "0.92rem", fontWeight: 500 }}
                >
                  Sort by
                </Typography>
                <Select
                  labelId="sort-by-label"
                  value={sortBy}
                  onChange={(e) => setSortBy(e.target.value as MemorySortBy)}
                >
                  <MenuItem value="updated_at">Last updated</MenuItem>
                  {activeTab === "area_to_improve" && (
                    <MenuItem value="priority">Priority</MenuItem>
                  )}
                </Select>
              </FormControl>

              <FormControl size="small" sx={{ minWidth: 0, ...textFieldStyles }}>
                <Typography
                  id="sort-direction-label"
                  component="label"
                  sx={{ mb: 0.75, color: "#cbd5e1", fontSize: "0.92rem", fontWeight: 500 }}
                >
                  Direction
                </Typography>
                <Select
                  labelId="sort-direction-label"
                  value={sortDirection}
                  onChange={(e) => setSortDirection(e.target.value as SortDirection)}
                >
                  <MenuItem value="asc">Ascending</MenuItem>
                  <MenuItem value="desc">Descending</MenuItem>
                </Select>
              </FormControl>
            </Box>

            <Box
              sx={{
                display: "flex",
                flex: "1 1 280px",
                minWidth: 0,
                alignItems: { xs: "stretch", lg: "center" },
                justifyContent: "space-between",
                gap: 1.25,
                flexWrap: "wrap",
              }}
            >
              <Typography
                variant="body2"
                sx={{ color: "#a5b4c7", whiteSpace: "nowrap", mr: { lg: 1 } }}
              >
                {displayedCountLabel}
              </Typography>

              <Box
                sx={{
                  display: "flex",
                  gap: 1,
                  flexWrap: "wrap",
                  justifyContent: { xs: "stretch", md: "flex-end" },
                  width: { xs: "100%", lg: "auto" },
                }}
              >
                <CustomButton
                  variant="secondary"
                  onClick={() => handleOpenForm()}
                  startIcon={<AddIcon />}
                  sx={{
                    border: "1px solid rgba(148, 163, 184, 0.2)",
                    bgcolor: "rgba(15, 23, 42, 0.34)",
                    color: "#e2e8f0",
                    px: 2.5,
                    width: { xs: "100%", sm: "auto" },
                    "&:hover": {
                      bgcolor: "rgba(15, 23, 42, 0.56)",
                      color: "white",
                    },
                  }}
                >
                  Add Item
                </CustomButton>
                {confirmClear ? (
                  <>
                    <CustomButton
                      variant="secondary"
                      onClick={async () => {
                        await clearCategory(activeTab);
                        setConfirmClear(false);
                      }}
                      disabled={items.length === 0}
                      sx={{
                        color: "#f87171",
                        border: "1px solid rgba(239, 68, 68, 0.18)",
                        bgcolor: "rgba(127, 29, 29, 0.16)",
                        width: { xs: "100%", sm: "auto" },
                        "&:hover": { bgcolor: "rgba(127, 29, 29, 0.28)" },
                      }}
                    >
                      Confirm Clear
                    </CustomButton>
                    <CustomButton
                      variant="secondary"
                      onClick={() => setConfirmClear(false)}
                      sx={{
                        border: "1px solid rgba(148, 163, 184, 0.2)",
                        width: { xs: "100%", sm: "auto" },
                      }}
                    >
                      Cancel
                    </CustomButton>
                  </>
                ) : (
                  <CustomButton
                    variant="secondary"
                    onClick={handleClearCategory}
                    disabled={items.length === 0}
                    sx={{
                      color: "#f87171",
                      width: { xs: "100%", sm: "auto" },
                      "&:hover": { bgcolor: "rgba(239, 68, 68, 0.1)" },
                    }}
                  >
                    Clear Category
                  </CustomButton>
                )}
              </Box>
            </Box>
          </Box>

          <Box
            ref={scrollContainerRef}
            onScroll={handleScroll}
            sx={{
              flexGrow: 1,
              overflowY: "auto",
              pr: { xs: 0.25, md: 0.5 },
              display: "flex",
              flexDirection: "column",
              gap: 2,
            }}
          >
            {error && (
              <Box
                sx={{
                  p: 2,
                  bgcolor: "rgba(239, 68, 68, 0.1)",
                  border: "1px solid #ef4444",
                  borderRadius: 1,
                }}
              >
                <Typography color="error">{error}</Typography>
              </Box>
            )}

            {items.length === 0 && !loading && (
              <Box sx={{ py: 8, textAlign: "center", color: "#6b7280" }}>
                <Typography variant="body1">
                  No memory items found in this category.
                </Typography>
                <Typography variant="body2">
                  The agent will add information here as you chat.
                </Typography>
              </Box>
            )}

            <Box
              sx={{
                display: "grid",
                gridTemplateColumns: { xs: "1fr", md: "1fr 1fr" },
                gap: 2,
              }}
            >
              {items.map((item) => (
                <Card
                  key={item.id}
                  sx={{
                    bgcolor: "rgba(30, 41, 59, 0.7)",
                    color: "white",
                    border: "1px solid rgba(148, 163, 184, 0.18)",
                    borderRadius: "1rem",
                    boxShadow: "inset 0 1px 0 rgba(255,255,255,0.03)",
                    backdropFilter: "blur(10px)",
                    "&:hover": { borderColor: "rgba(148, 163, 184, 0.3)" },
                  }}
                >
                  <CardContent
                    sx={{
                      p: { xs: 2, md: 2.5 },
                      pb: 1.5,
                      display: "flex",
                      flexDirection: "column",
                      gap: 2,
                    }}
                  >
                    <Box
                      sx={{
                        display: "grid",
                        gridTemplateColumns: { xs: "minmax(0, 1fr)", lg: "minmax(0, 1fr) auto" },
                        gap: 1.5,
                        alignItems: "flex-start",
                      }}
                    >
                      <Box sx={{ minWidth: 0, pr: { lg: 1 }, width: "100%" }}>
                        <Typography
                          variant="subtitle1"
                          fontWeight="bold"
                          sx={{
                            color: "var(--primary-color)",
                            fontSize: { xs: "1.1rem", md: "1.18rem" },
                            lineHeight: 1.35,
                            mb: 1.25,
                            overflowWrap: "anywhere",
                          }}
                        >
                          {getItemTitle(item)}
                        </Typography>
                        <Box
                          sx={{
                            display: "flex",
                            alignItems: "center",
                            gap: 0.75,
                            minWidth: 0,
                          }}
                        >
                          <Tooltip title={item.key}>
                            <Typography
                              variant="body2"
                              sx={{
                                color: "#94a3b8",
                                overflow: "hidden",
                                textOverflow: "ellipsis",
                                whiteSpace: "nowrap",
                                minWidth: 0,
                                fontSize: { xs: "0.88rem", md: "0.95rem" },
                              }}
                            >
                              {item.key}
                            </Typography>
                          </Tooltip>
                          <Tooltip title="Copy key">
                            <IconButton
                              size="small"
                              onClick={() => copyKeyToClipboard(item.key)}
                              sx={{
                                color: "#94a3b8",
                                p: 0.25,
                                "&:hover": { color: "white", bgcolor: "transparent" },
                              }}
                              aria-label="Copy memory item key"
                            >
                              <ContentCopyIcon fontSize="inherit" />
                            </IconButton>
                          </Tooltip>
                        </Box>
                      </Box>
                      <Box
                        sx={{
                          display: "flex",
                          alignItems: "flex-start",
                          gap: 0.75,
                          flexWrap: "wrap",
                          justifyContent: { xs: "flex-start", lg: "flex-end" },
                          width: "100%",
                          minWidth: 0,
                        }}
                      >
                        {/* Priority badge — area_to_improve only */}
                        {item.category === "area_to_improve" && (
                          editingPriorityId === item.id ? (
                            <Select
                              value={String(item.priority ?? "")}
                              size="small"
                              autoFocus
                              onChange={(e) => handlePriorityChange(item.id, e.target.value)}
                              onClose={() => setEditingPriorityId(null)}
                              aria-label="Priority selector"
                              sx={{
                                color: "white",
                                fontSize: "0.74rem",
                                height: 30,
                                minWidth: 78,
                                bgcolor: "rgba(15, 23, 42, 0.85)",
                                ".MuiOutlinedInput-notchedOutline": {
                                  borderColor: "rgba(148, 163, 184, 0.24)",
                                },
                                ".MuiSvgIcon-root": { color: "white" },
                              }}
                            >
                              {PRIORITY_OPTIONS.map((opt) => (
                                <MenuItem key={opt.value} value={opt.value} sx={{ fontSize: "0.75rem" }}>
                                  {opt.label}
                                </MenuItem>
                              ))}
                            </Select>
                          ) : (
                            <Tooltip title="Click to set priority">
                              <Chip
                                label={item.priority != null ? `P${item.priority}` : "P–"}
                                size="small"
                                onClick={() => setEditingPriorityId(item.id)}
                                aria-label="Priority badge"
                                sx={{
                                  height: 28,
                                  fontSize: "0.78rem",
                                  fontWeight: "bold",
                                  cursor: "pointer",
                                  borderRadius: "999px",
                                  ...getPriorityChipStyles(item.priority),
                                  "&:hover": { opacity: 0.8 },
                                }}
                              />
                            </Tooltip>
                          )
                        )}
                        <Chip
                          label={
                            STATUS_OPTIONS[item.status]?.label || item.status
                          }
                          size="small"
                          sx={{
                            height: 28,
                            fontSize: "0.8rem",
                            fontWeight: "bold",
                            borderRadius: "999px",
                            ...getStatusChipStyles(item.status),
                          }}
                        />
                      </Box>
                    </Box>
                    <Typography
                      variant="body1"
                      sx={{
                        whiteSpace: "pre-wrap",
                        color: "#e2e8f0",
                        lineHeight: 1.65,
                        minHeight: { md: 110 },
                      }}
                    >
                      {item.content}
                    </Typography>
                    <Divider sx={{ borderColor: "rgba(148, 163, 184, 0.14)" }} />
                    <Box
                      sx={{
                        display: "flex",
                        justifyContent: "space-between",
                        alignItems: "center",
                        gap: 1,
                        flexWrap: "wrap",
                      }}
                    >
                      <Box sx={{ display: "flex", alignItems: "center", gap: 0.85, color: "#94a3b8" }}>
                        <CalendarTodayOutlinedIcon sx={{ fontSize: "0.95rem" }} />
                        <Typography variant="body2" sx={{ fontSize: "0.95rem", color: "#94a3b8" }}>
                          Updated {new Date(item.updated_at).toLocaleDateString(MEMORY_DATE_LOCALE)}
                        </Typography>
                      </Box>
                      <CardActions sx={{ justifyContent: "flex-end", p: 0, gap: 0.25 }}>
                        {item.category === "area_to_improve" &&
                          item.status === "mastered" && (
                            <Tooltip title="Promote to Strength">
                              <IconButton
                                size="small"
                                onClick={() => handlePromote(item.id)}
                                sx={{ color: "var(--primary-color)" }}
                              >
                                <TrendingUpIcon fontSize="small" />
                              </IconButton>
                            </Tooltip>
                          )}
                        <IconButton
                          size="small"
                          onClick={() => handleOpenForm(item)}
                          sx={{ color: "#9ca3af" }}
                        >
                          <EditIcon fontSize="small" />
                        </IconButton>
                        {confirmDeleteId === item.id ? (
                          <>
                            <IconButton
                              size="small"
                              onClick={async () => {
                                await deleteItem(item.id);
                                setConfirmDeleteId(null);
                              }}
                              aria-label="Confirm delete"
                              sx={{ color: "#ef4444" }}
                            >
                              <CheckIcon fontSize="small" />
                            </IconButton>
                            <IconButton
                              size="small"
                              onClick={() => setConfirmDeleteId(null)}
                              aria-label="Cancel delete"
                              sx={{ color: "#9ca3af" }}
                            >
                              <CloseIcon fontSize="small" />
                            </IconButton>
                          </>
                        ) : (
                          <IconButton
                            size="small"
                            onClick={() => handleDelete(item.id)}
                            aria-label="Delete item"
                            sx={{ color: "#ef4444" }}
                          >
                            <DeleteIcon fontSize="small" />
                          </IconButton>
                        )}
                      </CardActions>
                    </Box>
                  </CardContent>
                </Card>
              ))}
            </Box>

            <Box
              sx={{
                display: "flex",
                alignItems: "center",
                gap: 1.25,
                px: { xs: 1.5, md: 2 },
                py: 1.5,
                borderRadius: "0.95rem",
                border: "1px solid rgba(148, 163, 184, 0.16)",
                bgcolor: "rgba(30, 41, 59, 0.45)",
              }}
            >
              <LightbulbOutlinedIcon
                sx={{ color: "var(--primary-color)", fontSize: "1.05rem", flexShrink: 0 }}
              />
              <Typography
                variant="body2"
                sx={{ color: "#cbd5e1", fontSize: { xs: "0.92rem", md: "0.98rem" } }}
              >
                {CATEGORY_HELP_TEXT[activeTab]}
              </Typography>
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
          },
        }}
      >
        <DialogTitle>
          {editingItem ? "Edit Memory Item" : "Add Memory Item"}
        </DialogTitle>
        <DialogContent
          sx={{
            display: "flex",
            flexDirection: "column",
            gap: 3,
            pt: 2,
            minWidth: 400,
          }}
        >
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
            onChange={(e) =>
              setFormData({ ...formData, content: e.target.value })
            }
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
              {renderStatusMenuItems(formData.category)}
            </Select>
          </FormControl>
          {/* Priority — only for area_to_improve */}
          {formData.category === "area_to_improve" && (
            <FormControl fullWidth sx={textFieldStyles}>
              <InputLabel id="form-priority-label">Priority</InputLabel>
              <Select
                labelId="form-priority-label"
                value={formData.priority !== null && formData.priority !== undefined ? String(formData.priority) : ""}
                label="Priority"
                onChange={(e) =>
                  setFormData({
                    ...formData,
                    priority: e.target.value === "" ? null : Number(e.target.value),
                  })
                }
              >
                {PRIORITY_OPTIONS.map((opt) => (
                  <MenuItem key={opt.value} value={opt.value}>
                    {opt.label}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>
          )}
        </DialogContent>
        <DialogActions sx={{ p: 3 }}>
          <CustomButton
            variant="secondary"
            onClick={() => setIsFormOpen(false)}
          >
            Cancel
          </CustomButton>
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
