import React from "react";
import { Box, Typography, Table, TableBody, TableCell, TableContainer, TableHead, TableRow, Paper, CircularProgress, Alert } from "@mui/material";
import useVocabulary from "../hooks/useVocabulary";

const VocabularyView: React.FC = () => {
  const { vocabulary, loading, error } = useVocabulary();

  if (loading) {
    return (
      <Box sx={{ display: "flex", justifyContent: "center", alignItems: "center", minHeight: "200px" }}>
        <CircularProgress sx={{ color: "var(--primary-color)" }} />
      </Box>
    );
  }

  if (error) {
    return (
      <Box sx={{ maxWidth: "64rem", mx: "auto", mt: 8 }}>
        <Alert severity="error">
          {error}
        </Alert>
      </Box>
    );
  }

  return (
    <Box sx={{ py: 8 }}>
      <Typography
        variant="h4"
        sx={{ mb: 4, color: "white", fontWeight: "bold" }}
      >
        Saved Vocabulary
      </Typography>

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
        <Box sx={{ mt: 4 }}>
          <TableContainer component={Paper} sx={{ backgroundColor: "#2a1f35", borderRadius: "0.5rem" }}>
            <Table>
              <TableHead>
                <TableRow>
                  <TableCell sx={{ color: "white", fontWeight: "bold", borderBottom: "1px solid #4d3c63" }}>
                    Swedish
                  </TableCell>
                  <TableCell sx={{ color: "white", fontWeight: "bold", borderBottom: "1px solid #4d3c63" }}>
                    English
                  </TableCell>
                  <TableCell sx={{ color: "white", fontWeight: "bold", borderBottom: "1px solid #4d3c63" }}>
                    Example Phrase
                  </TableCell>
                  <TableCell sx={{ color: "white", fontWeight: "bold", borderBottom: "1px solid #4d3c63" }}>
                    Saved
                  </TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {vocabulary.map((item) => (
                  <TableRow key={item.id} sx={{ borderBottom: "1px solid #4d3c63" }}>
                    <TableCell sx={{ color: "white", borderBottom: "1px solid #4d3c63" }}>
                      {item.word_phrase}
                    </TableCell>
                    <TableCell sx={{ color: "#9ca3af", borderBottom: "1px solid #4d3c63" }}>
                      {item.translation}
                    </TableCell>
                    <TableCell sx={{ color: "#9ca3af", borderBottom: "1px solid #4d3c63" }}>
                      {item.example_phrase || "—"}
                    </TableCell>
                    <TableCell sx={{ color: "#6b7280", borderBottom: "1px solid #4d3c63" }}>
                      {new Date(item.created_at).toLocaleDateString()}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
        </Box>
      )}
    </Box>
  );
};

export default VocabularyView;