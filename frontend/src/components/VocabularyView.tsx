import React, { useState, useEffect } from "react";
import { Box, Typography } from "@mui/material";
import { useRecentVocabulary, useVocabularyStats } from "../hooks/useVocabulary";
import {
  LoadingSpinner,
  ErrorAlert,
  SectionTitle,
  DataTable,
  StyledCheckbox,
  SearchInput,
  CustomButton,
} from "./ui";
import AddEditVocabularyModal from "./AddEditVocabularyModal";

const statCards = [
  { key: "words_in_learn_count", label: "Words Studied" },
  { key: "words_skipped_count", label: "Words Skipped" },
  { key: "overall_words_count", label: "Overall Words" },
  { key: "words_prioritized_count", label: "Prioritised Words" },
] as const;

const VocabularyView: React.FC = () => {
  const [searchTerm, setSearchTerm] = useState("");
  const [activeSearchTerm, setActiveSearchTerm] = useState("");
  const [preciseSearch, setPreciseSearch] = useState(false);
  const [isInitialLoad, setIsInitialLoad] = useState(true);
  const {
    stats,
    loading: statsLoading,
    error: statsError,
    refetch: refetchStats,
  } = useVocabularyStats();
  const {
    recentVocabulary,
    loading,
    error,
    isEditModalOpen,
    editingItem,
    openEditModal,
    closeEditModal,
    updateVocabularyItem,
    createVocabularyItem,
    deleteVocabularyItem,
  } = useRecentVocabulary(activeSearchTerm, preciseSearch);

  useEffect(() => {
    if (!loading && isInitialLoad) {
      setIsInitialLoad(false);
    }
  }, [loading, isInitialLoad]);

  useEffect(() => {
    if (searchTerm.length > 3) {
      setActiveSearchTerm(searchTerm);
    } else if (searchTerm.length === 0) {
      setActiveSearchTerm("");
    }
  }, [searchTerm]);

  const handleSearch = () => {
    setActiveSearchTerm(searchTerm);
  };

  const handleClearSearch = () => {
    setSearchTerm("");
    setActiveSearchTerm("");
  };

  const handleRowClick = (row: unknown) => {
    const item = row as (typeof recentVocabulary)[0];
    openEditModal(item);
  };

  const handleSaveEdit = async (
    updatedItem: Partial<(typeof recentVocabulary)[0]>
  ) => {
    if (editingItem) {
      await updateVocabularyItem(editingItem.id, updatedItem);
    } else {
      await createVocabularyItem(updatedItem);
    }
    await refetchStats();
  };

  const handleDelete = async () => {
    if (editingItem) {
      await deleteVocabularyItem(editingItem.id);
      await refetchStats();
    }
  };

  // Only show full-page loading spinner on initial load
  if (loading && isInitialLoad) {
    return <LoadingSpinner />;
  }

  if (error) {
    return <ErrorAlert message={error} />;
  }

  return (
    <Box sx={{ py: 8 }}>
      <SectionTitle>Recent Vocabulary</SectionTitle>

      {statsError ? (
        <ErrorAlert message={statsError} />
      ) : (
        <Box
          sx={{
            display: "grid",
            gridTemplateColumns: {
              xs: "1fr",
              sm: "repeat(2, minmax(0, 1fr))",
              lg: "repeat(4, minmax(0, 1fr))",
            },
            gap: 1,
            mb: 2.5,
          }}
        >
          {statCards.map((card) => (
            <Box
              key={card.key}
              sx={{
                p: 1.25,
                borderRadius: 1.5,
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
                gap: 1,
                background:
                  "linear-gradient(180deg, rgba(255,255,255,0.08) 0%, rgba(255,255,255,0.03) 100%)",
                border: "1px solid rgba(255,255,255,0.08)",
                backdropFilter: "blur(10px)",
              }}
            >
              <Typography
                sx={{
                  color: "rgba(255, 255, 255, 0.7)",
                  fontSize: "0.75rem",
                  mb: 0,
                }}
              >
                {card.label}
              </Typography>
              <Typography
                sx={{
                  color: "white",
                  fontSize: { xs: "1.05rem", sm: "1.2rem" },
                  fontWeight: 700,
                  lineHeight: 1.1,
                  whiteSpace: "nowrap",
                }}
              >
                {statsLoading || !stats ? "..." : stats[card.key]}
              </Typography>
            </Box>
          ))}
        </Box>
      )}

      <Box
        sx={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "flex-start",
          mb: 3,
          gap: 2,
        }}
      >
        <Box
          sx={{
            display: "flex",
            flexDirection: "column",
            gap: 1,
            flex: 1,
          }}
        >
          <SearchInput
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            placeholder="Search vocabulary..."
            onSearch={handleSearch}
            onClear={handleClearSearch}
            sx={{ mb: 0 }}
          />
          <StyledCheckbox
            id="precise-search-checkbox"
            checked={preciseSearch}
            onChange={setPreciseSearch}
            label="Precise search"
          />
        </Box>
        <CustomButton variant="primary" onClick={() => openEditModal(null)}>
          Add New Word
        </CustomButton>
      </Box>

      {loading && !isInitialLoad && (
        <Box sx={{ display: "flex", justifyContent: "center", my: 2 }}>
          <Typography sx={{ color: "#9ca3af" }}>Loading...</Typography>
        </Box>
      )}

      {recentVocabulary.length === 0 && !loading ? (
        <Box sx={{ textAlign: "center", py: 8 }}>
          <Typography sx={{ color: "#9ca3af", mb: 2 }}>
            {activeSearchTerm
              ? "No vocabulary matches your search."
              : "No vocabulary saved yet."}
          </Typography>
          <Typography sx={{ color: "#6b7280" }}>
            {activeSearchTerm
              ? "Try a different search term."
              : "Analyze some text and save vocabulary items to see them here."}
          </Typography>
        </Box>
      ) : (
        recentVocabulary.length > 0 && (
          <DataTable
            columns={[
              { key: "word_phrase", label: "Swedish" },
              { key: "translation", label: "English" },
              { key: "example_phrase", label: "Example Phrase" },
              {
                key: "extra_info",
                label: "Grammar Info",
                render: (value) => (value as string | null) || "—",
              },
              {
                key: "in_learn",
                label: "In Learning",
                render: (value) => (
                  <StyledCheckbox
                    checked={value as boolean}
                    onChange={() => {}} // TODO: Implement update functionality
                    sx={{ pointerEvents: "none" }} // Make it read-only for now
                  />
                ),
              },
              {
                key: "priority_learn",
                label: "Priority",
                render: (value) => <Typography sx={{ color: "white", textAlign: "center" }}>{value as number}</Typography>,
              },
              {
                key: "last_learned",
                label: "Last Learned",
                render: (value) => (
                  <Typography sx={{ color: "white", textAlign: "center" }}>
                    {value
                      ? new Date(value as string).toLocaleDateString()
                      : "Never"}
                  </Typography>
                ),
              },
              {
                key: "learned_times",
                label: "Learned Times",
                render: (value) => (
                  <Typography sx={{ color: "white", textAlign: "center" }}>
                    {value as number}
                  </Typography>
                ),
              },
              {
                key: "created_at",
                label: "Saved",
                render: (value) =>
                  new Date(value as string).toLocaleDateString(),
              },
            ]}
            data={
              recentVocabulary.map((item) => ({
                ...item,
                id: item.id,
              })) as unknown as ({ id: string } & Record<string, unknown>)[]
            }
            onRowClick={handleRowClick}
          />
        )
      )}

      <AddEditVocabularyModal
        open={isEditModalOpen}
        item={editingItem}
        onClose={closeEditModal}
        onSave={handleSaveEdit}
        onDelete={handleDelete}
      />
    </Box>
  );
};

export default VocabularyView;
