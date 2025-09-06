import React, { useState } from "react";
import {
  Box,
  Typography,
  Button,
} from "@mui/material";
import { Copy, AlertTriangle } from "lucide-react";

interface OCRResult {
  text: string;
  character_count: number;
}

interface GrammarFocus {
  topic: string;
  explanation: string;
  has_explicit_rules: boolean;
}

interface VocabularyItem {
  swedish: string;
  english: string;
}

interface ContentAnalysis {
  grammar_focus: GrammarFocus;
  vocabulary: VocabularyItem[];
}

interface ProcessingResult {
  ocr_result: OCRResult;
  analysis: ContentAnalysis;
  extra_info?: string;
  processing_successful: boolean;
}

interface ResultsDisplayProps {
  result: ProcessingResult | null;
  error: string | null;
}

const ResultsDisplay: React.FC<ResultsDisplayProps> = ({ result, error }) => {
  const [activeTab, setActiveTab] = useState("ocr");

  if (error) {
    return (
      <Box sx={{ maxWidth: '64rem', mx: 'auto', mt: 8 }}>
        <Box
          sx={{
            backgroundColor: 'rgba(220, 38, 38, 0.1)',
            border: '1px solid #dc2626',
            borderRadius: '0.75rem',
            p: 6,
          }}
        >
          <Box sx={{ display: 'flex', alignItems: 'flex-start' }}>
            <Box sx={{ flexShrink: 0 }}>
              <Box
                sx={{
                  width: 10,
                  height: 10,
                  backgroundColor: 'rgba(220, 38, 38, 0.5)',
                  borderRadius: '50%',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                }}
              >
                <AlertTriangle size={20} style={{ color: '#ef4444' }} />
              </Box>
            </Box>
            <Box sx={{ ml: 4 }}>
              <Typography
                variant="body1"
                sx={{
                  fontSize: '1.125rem',
                  fontWeight: 600,
                  color: '#ef4444',
                  mb: 1,
                }}
              >
                Processing Error
              </Typography>
              <Box sx={{ color: '#dc2626' }}>
                <Typography>{error}</Typography>
              </Box>
            </Box>
          </Box>
        </Box>
      </Box>
    );
  }

  if (!result) {
    return null;
  }

  const handleCopyVocabulary = () => {
    const vocabText = result.analysis.vocabulary
      .map((item) => `${item.swedish} - ${item.english}`)
      .join("\n");
    navigator.clipboard.writeText(vocabText);
  };

  const tabs = [
    { id: "ocr", label: "OCR Text" },
    { id: "grammar", label: "Grammar" },
    { id: "vocabulary", label: "Vocabulary" },
    { id: "extra_info", label: "Extra info" },
  ];

  return (
    <Box sx={{ py: 8 }}>
      <Typography variant="h3" sx={{ mb: 4, color: 'white', fontWeight: 'bold' }}>
        Analysis Results
      </Typography>

      <Box sx={{ borderBottom: '1px solid #4d3c63' }}>
        <Box sx={{ display: 'flex', mb: '-1px', gap: 8 }}>
          {tabs.map((tab) => (
            <Button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              sx={{
                px: 1,
                py: 4,
                borderBottom: activeTab === tab.id ? '2px solid var(--primary-color)' : '2px solid transparent',
                color: activeTab === tab.id ? 'var(--primary-color)' : '#9ca3af',
                fontWeight: 'medium',
                fontSize: '0.875rem',
                textTransform: 'none',
                '&:hover': {
                  color: 'white',
                  borderBottomColor: activeTab === tab.id ? 'var(--primary-color)' : '#6b7280',
                },
                transition: 'color 0.2s, border-color 0.2s',
              }}
            >
              {tab.label}
            </Button>
          ))}
        </Box>
      </Box>

      <Box sx={{ pt: 6 }}>
        {activeTab === "ocr" && (
          <Box>
            <Typography sx={{ color: '#d1d5db', mb: 2 }}>
              The OCR text extracted from the image will be displayed here.
              This text can be edited and copied for further use.
            </Typography>
            {result && (
              <Box sx={{ mt: 4, p: 4, backgroundColor: '#2a1f35', borderRadius: '0.5rem' }}>
                <Typography sx={{ color: 'white', whiteSpace: 'pre-wrap' }}>
                  {result.ocr_result.text}
                </Typography>
              </Box>
            )}
          </Box>
        )}

        {activeTab === "grammar" && (
          <Box>
            <Typography variant="h4" sx={{ mb: 3, color: 'white' }}>
              Grammar Analysis
            </Typography>
            {result && (
              <Box sx={{ mt: 4, display: 'flex', flexDirection: 'column', gap: 4 }}>
                <Box sx={{ p: 4, backgroundColor: '#2a1f35', borderRadius: '0.5rem' }}>
                  <Typography sx={{ color: 'var(--primary-color)', fontWeight: 'bold', mb: 1 }}>
                    Topic:
                  </Typography>
                  <Typography sx={{ color: 'white' }}>
                    {result.analysis.grammar_focus.topic}
                  </Typography>
                </Box>
                <Box sx={{ p: 4, backgroundColor: '#2a1f35', borderRadius: '0.5rem' }}>
                  <Typography sx={{ color: 'var(--primary-color)', fontWeight: 'bold', mb: 1 }}>
                    Explanation:
                  </Typography>
                  <Typography sx={{ color: 'white' }}>
                    {result.analysis.grammar_focus.explanation}
                  </Typography>
                </Box>
                <Box sx={{ p: 4, backgroundColor: '#2a1f35', borderRadius: '0.5rem' }}>
                  <Typography sx={{ color: 'var(--primary-color)', fontWeight: 'bold', mb: 1 }}>
                    Has Explicit Rules:
                  </Typography>
                  <Typography sx={{ color: 'white' }}>
                    {result.analysis.grammar_focus.has_explicit_rules ? "Yes" : "No"}
                  </Typography>
                </Box>
              </Box>
            )}
          </Box>
        )}

        {activeTab === "vocabulary" && (
          <Box>
            <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 4 }}>
              <Typography variant="h4" sx={{ color: 'white' }}>
                Vocabulary Analysis
              </Typography>
              {result && result.analysis.vocabulary.length > 0 && (
                <Button
                  onClick={handleCopyVocabulary}
                  sx={{
                    px: 4,
                    py: 2,
                    backgroundColor: 'var(--primary-color)',
                    color: 'white',
                    borderRadius: '0.5rem',
                    fontWeight: 700,
                    display: 'flex',
                    alignItems: 'center',
                    gap: 2,
                    '&:hover': {
                      backgroundColor: 'var(--primary-color)',
                      opacity: 0.9,
                      transform: 'scale(1.05)',
                      boxShadow: '0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -2px rgba(0, 0, 0, 0.05)',
                    },
                    '&:active': {
                      transform: 'scale(0.95)',
                    },
                    transition: 'all 0.2s',
                  }}
                >
                  <Copy size={16} />
                  Copy
                </Button>
              )}
            </Box>
            {result && (
              <Box sx={{ mt: 4, display: 'flex', flexDirection: 'column', gap: 2 }}>
                {result.analysis.vocabulary.map((item, index) => (
                  <Box
                    key={index}
                    sx={{
                      p: 4,
                      backgroundColor: '#2a1f35',
                      borderRadius: '0.5rem',
                      display: 'flex',
                      justifyContent: 'space-between',
                      alignItems: 'center',
                    }}
                  >
                    <Typography sx={{ color: 'white', fontWeight: 'bold' }}>
                      {item.swedish}
                    </Typography>
                    <Typography sx={{ color: '#9ca3af' }}>
                      {item.english}
                    </Typography>
                  </Box>
                ))}
              </Box>
            )}
          </Box>
        )}

        {activeTab === "extra_info" && (
          <Box>
            <Typography variant="h4" sx={{ mb: 3, color: 'white' }}>
              Extra info
            </Typography>
            {result && result.extra_info ? (
              <Box sx={{ mt: 4, p: 4, backgroundColor: '#2a1f35', borderRadius: '0.5rem' }}>
                <Typography sx={{ color: 'white', whiteSpace: 'pre-wrap' }}>
                  {result.extra_info}
                </Typography>
              </Box>
            ) : (
              <Typography sx={{ color: '#d1d5db' }}>
                Additional learning materials and resources will be displayed here.
              </Typography>
            )}
          </Box>
        )}
      </Box>
    </Box>
  );
};

export default ResultsDisplay;
