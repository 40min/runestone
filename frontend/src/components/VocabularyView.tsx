import React, { useState, useEffect } from "react";
import { Box, Typography } from "@mui/material";
import { useRecentVocabulary } from "../hooks/useVocabulary";
import { LoadingSpinner, ErrorAlert, SectionTitle, DataTable, StyledCheckbox, SearchInput } from "./ui";

const VocabularyView: React.FC = () => {
  const [searchTerm, setSearchTerm] = useState("");
  const [debouncedSearchTerm, setDebouncedSearchTerm] = useState("");
  const { recentVocabulary, loading, error } = useRecentVocabulary(debouncedSearchTerm);

  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedSearchTerm(searchTerm);
    }, 300);

    return () => clearTimeout(timer);
  }, [searchTerm]);

  if (loading) {
    return <LoadingSpinner />;
  }

  if (error) {
    return <ErrorAlert message={error} />;
  }

  return (
    <Box sx={{ py: 8 }}>
      <SectionTitle>Recent Vocabulary</SectionTitle>

      <SearchInput
        value={searchTerm}
        onChange={(e) => setSearchTerm(e.target.value)}
        placeholder="Search vocabulary..."
      />

      {recentVocabulary.length === 0 ? (
        <Box sx={{ textAlign: "center", py: 8 }}>
          <Typography sx={{ color: "#9ca3af", mb: 2 }}>
            {debouncedSearchTerm ? "No vocabulary matches your search." : "No vocabulary saved yet."}
          </Typography>
          <Typography sx={{ color: "#6b7280" }}>
            {debouncedSearchTerm
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
              key: 'showed_times',
              label: 'Shown Times',
              render: (value) => (
                <Typography sx={{ color: 'white', textAlign: 'center' }}>
                  {value as number}
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
        />
      )}
    </Box>
  );
};

export default VocabularyView;