import React from "react";
import { Box, Typography } from "@mui/material";
import useVocabulary from "../hooks/useVocabulary";
import { LoadingSpinner, ErrorAlert, SectionTitle, DataTable } from "./ui";

const VocabularyView: React.FC = () => {
  const { vocabulary, loading, error } = useVocabulary();

  if (loading) {
    return <LoadingSpinner />;
  }

  if (error) {
    return <ErrorAlert message={error} />;
  }

  return (
    <Box sx={{ py: 8 }}>
      <SectionTitle>Saved Vocabulary</SectionTitle>

      {vocabulary.length === 0 ? (
        <Box sx={{ textAlign: "center", py: 8 }}>
          <Typography sx={{ color: "#9ca3af", mb: 2 }}>
            No vocabulary saved yet.
          </Typography>
          <Typography sx={{ color: "#6b7280" }}>
            Analyze some text and save vocabulary items to see them here.
          </Typography>
        </Box>
      ) : (
        <DataTable
          columns={[
            { key: 'word_phrase', label: 'Swedish' },
            { key: 'translation', label: 'English' },
            { key: 'example_phrase', label: 'Example Phrase' },
            {
              key: 'created_at',
              label: 'Saved',
              render: (value) => new Date(value).toLocaleDateString()
            },
          ]}
          data={vocabulary}
        />
      )}
    </Box>
  );
};

export default VocabularyView;