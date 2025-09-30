import React, { useState, useEffect } from "react";
import { Box, Typography } from "@mui/material";
import { useRecentVocabulary } from "../hooks/useVocabulary";
import { LoadingSpinner, ErrorAlert, SectionTitle, DataTable, StyledCheckbox, SearchInput, CustomButton } from "./ui";
import AddEditVocabularyModal from "./AddEditVocabularyModal";

const VocabularyView: React.FC = () => {
  const [searchTerm, setSearchTerm] = useState("");
  const [activeSearchTerm, setActiveSearchTerm] = useState("");
  const [isInitialLoad, setIsInitialLoad] = useState(true);
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
  } = useRecentVocabulary(activeSearchTerm);

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

  const handleRowClick = (row: unknown) => {
    const item = row as typeof recentVocabulary[0];
    openEditModal(item);
  };

  const handleSaveEdit = async (updatedItem: Partial<typeof recentVocabulary[0]>) => {
    if (editingItem) {
      await updateVocabularyItem(editingItem.id, updatedItem);
    } else {
      await createVocabularyItem(updatedItem);
    }
  };

  const handleDelete = async () => {
    if (editingItem) {
      await deleteVocabularyItem(editingItem.id);
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

      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', mb: 3 }}>
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

      {loading && !isInitialLoad && (
        <Box sx={{ display: 'flex', justifyContent: 'center', my: 2 }}>
          <Typography sx={{ color: "#9ca3af" }}>Loading...</Typography>
        </Box>
      )}
      
      {recentVocabulary.length === 0 && !loading ? (
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
        recentVocabulary.length > 0 && (
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