import { useState } from "react";
import { Box, CircularProgress, Stack, Typography } from "@mui/material";
import { useRecall } from "../hooks/useRecall";
import type { SavedVocabularyItem } from "../hooks/useVocabulary";
import { useApi } from "../utils/api";
import {
  CustomButton,
  ErrorAlert,
  SectionTitle,
  Snackbar,
} from "./ui";
import AddEditVocabularyModal from "./AddEditVocabularyModal";
import RecallQueuePanel from "./recall/RecallQueuePanel";
import RecallSummaryPanel from "./recall/RecallSummaryPanel";
import RecallDeliverySchedule from "./recall/RecallDeliverySchedule";

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
    saveSchedule,
    setDeliveryEnabled,
    clearFeedback,
    feedbackAction,
  } = useRecall();
  const { get, put, delete: apiDelete } = useApi();
  const isMutating = pendingAction !== null;

  const [isEditModalOpen, setIsEditModalOpen] = useState(false);
  const [editingItem, setEditingItem] = useState<SavedVocabularyItem | null>(
    null
  );
  const [editError, setEditError] = useState<string | null>(null);

  const getVocabularyItem = async (
    itemId: number
  ): Promise<SavedVocabularyItem | null> => {
    return get<SavedVocabularyItem>(`/api/vocabulary/${itemId}`);
  };

  const lookupVocabularyItem = async (
    wordPhrase: string
  ): Promise<SavedVocabularyItem | null> => {
    const trimmedWordPhrase = wordPhrase.trim();
    if (!trimmedWordPhrase) {
      return null;
    }

    const params = new URLSearchParams({
      search_query: trimmedWordPhrase,
      limit: "20",
      precise: "true",
    });
    const data = await get<SavedVocabularyItem[]>(
      `/api/vocabulary?${params.toString()}`
    );
    const exactCaseMatch = data.find(
      (item) => item.word_phrase === trimmedWordPhrase
    );
    return exactCaseMatch ?? data[0] ?? null;
  };

  const handleEditWord = async (word: {
    id: number;
    word_phrase: string;
  }) => {
    setEditError(null);
    try {
      const item = await getVocabularyItem(word.id);
      setEditingItem(item);
      setIsEditModalOpen(true);
    } catch (editError_) {
      setEditError(
        editError_ instanceof Error
          ? editError_.message
          : "Failed to load vocabulary item"
      );
    }
  };

  const handleCloseEditModal = () => {
    setIsEditModalOpen(false);
    setEditingItem(null);
  };

  const handleSaveEdit = async (updatedItem: Partial<SavedVocabularyItem>) => {
    if (!editingItem) return;
    await put<SavedVocabularyItem>(
      `/api/vocabulary/${editingItem.id}`,
      updatedItem
    );
    handleCloseEditModal();
    await refetch();
  };

  const handleDeleteEdit = async () => {
    if (!editingItem) return;
    await apiDelete(`/api/vocabulary/${editingItem.id}`);
    handleCloseEditModal();
    await refetch();
  };

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
          onEdit={handleEditWord}
          onPostpone={(id, phrase) => void postponeWord(id, phrase)}
          onRemove={(id, phrase) => void removeWord(id, phrase)}
        />
      </Box>

      <RecallDeliverySchedule
        recall={recall}
        disabled={!recall.configured || isMutating}
        pendingAction={pendingAction}
        error={error}
        success={success}
        feedbackAction={feedbackAction}
        onSaveTimes={(startHour, endHour) =>
          void saveSchedule(startHour, endHour)
        }
        onToggleDelivery={(enabled, startHour, endHour) =>
          void setDeliveryEnabled(enabled, startHour, endHour)
        }
      />

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
      <Snackbar
        open={Boolean(editError)}
        message={editError ?? ""}
        severity="error"
        onClose={() => setEditError(null)}
      />

      <AddEditVocabularyModal
        open={isEditModalOpen}
        item={editingItem}
        onClose={handleCloseEditModal}
        onSave={handleSaveEdit}
        onDelete={handleDeleteEdit}
        onLookup={lookupVocabularyItem}
        onLookupFound={setEditingItem}
      />
    </Box>
  );
};

export default RecallView;
