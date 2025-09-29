import React, { useState, useEffect } from "react";
import { Box, Typography } from "@mui/material";
import { useRecentVocabulary } from "../hooks/useVocabulary";
import { LoadingSpinner, ErrorAlert, SectionTitle, DataTable, StyledCheckbox, SearchInput, CustomButton } from "./ui";
import AddEditVocabularyModal from "./AddEditVocabularyModal";

const VocabularyView: React.FC = () => {
  const [searchTerm, setSearchTerm] = useState("");
  const [activeSearchTerm, setActiveSearchTerm] = useState("");
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
  } = useRecentVocabulary(activeSearchTerm);

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

  const handleRowClick = (row: unknown) => {
    const item = row as typeof recentVocabulary[0];
    openEditModal(item);
  };

  const handleSaveEdit = (updatedItem: Partial<typeof recentVocabulary[0]>) => {
    if (editingItem) {
      updateVocabularyItem(editingItem.id, updatedItem);
    } else {
      createVocabularyItem(updatedItem);
    }
  };

  if (loading) {
    return <LoadingSpinner />;
  }

  if (error) {
    return <ErrorAlert message={error} />;
  }

  return (
    <Box sx={{ py: 8 }}>
      <SectionTitle>Recent Vocabulary</SectionTitle>

      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
        <SearchInput
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
          placeholder="Search vocabulary..."
          onSearch={handleSearch}
        />
        <CustomButton variant="primary" onClick={() => openEditModal(null)}>
          Add New Word
        </CustomButton>
      </Box>

      {recentVocabulary.length === 0 ? (
        <Box sx={{ textAlign: "center", py: 8 }}>
          <Typography sx={{ color: "#9ca3af", mb: 2 }}>
            {activeSearchTerm ? "No vocabulary matches your search." : "No vocabulary saved yet."}
          </Typography>
          <Typography sx={{ color: "#6b7280" }}>
            {activeSearchTerm
              ? "Try a different search term."
              : "Analyze some text and save vocabulary items to see them here."}
          </Typography>
        </Box>
      ) : (
        <DataTable
          columns={[
            { key: 'word_phrase', label: 'Swedish' },
            { key: 'translation', label: 'English' },
            { key: 'example_phrase', label: 'Example Phrase' },
            {
              key: 'in_learn',
              label: 'In Learning',
              render: (value) => (
                <StyledCheckbox
                  checked={value as boolean}
                  onChange={() => {}} // TODO: Implement update functionality
                  sx={{ pointerEvents: 'none' }} // Make it read-only for now
                />
              )
            },
            {
              key: 'last_learned',
              label: 'Last Learned',
              render: (value) => (
                <Typography sx={{ color: 'white', textAlign: 'center' }}>
                  {value ? new Date(value as string).toLocaleDateString() : 'Never'}
                </Typography>
              )
            },
            {
              key: 'created_at',
              label: 'Saved',
              render: (value) => new Date(value as string).toLocaleDateString()
            },
          ]}
          data={recentVocabulary as unknown as Record<string, unknown>[]}
          onRowClick={handleRowClick}
        />
      )}

      <AddEditVocabularyModal
        open={isEditModalOpen}
        item={editingItem}
        onClose={closeEditModal}
        onSave={handleSaveEdit}
      />
    </Box>
  );
};

export default VocabularyView;