import React, { useState, useEffect } from 'react';
import {
  Modal,
  Box,
  TextField,
  Typography,
  IconButton,
} from '@mui/material';
import { CustomButton, StyledCheckbox } from './ui';
import { improveVocabularyItem } from '../hooks/useVocabulary';

interface SavedVocabularyItem {
  id: number;
  user_id: number;
  word_phrase: string;
  translation: string;
  example_phrase: string | null;
  in_learn: boolean;
  last_learned: string | null;
  created_at: string;
}

interface AddEditVocabularyModalProps {
  open: boolean;
  item: SavedVocabularyItem | null;
  onClose: () => void;
  onSave: (updatedItem: Partial<SavedVocabularyItem>) => Promise<void>;
  onDelete?: () => Promise<void>;
}

const AddEditVocabularyModal: React.FC<AddEditVocabularyModalProps> = ({
  open,
  item,
  onClose,
  onSave,
  onDelete,
}) => {
  const [wordPhrase, setWordPhrase] = useState('');
  const [translation, setTranslation] = useState('');
  const [examplePhrase, setExamplePhrase] = useState('');
  const [inLearn, setInLearn] = useState(false);
  const [isImproving, setIsImproving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setError(null);
    if (item) {
      setWordPhrase(item.word_phrase);
      setTranslation(item.translation);
      setExamplePhrase(item.example_phrase || '');
      setInLearn(item.in_learn);
    } else {
      setWordPhrase('');
      setTranslation('');
      setExamplePhrase('');
      setInLearn(false);
    }
  }, [item, open]);

  const handleSave = async () => {
    if (!wordPhrase.trim() || !translation.trim()) {
      return; // Basic validation
    }

    try {
      await onSave({
        word_phrase: wordPhrase.trim(),
        translation: translation.trim(),
        example_phrase: examplePhrase.trim() || null,
        in_learn: inLearn,
      });
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to save vocabulary item';
      setError(errorMessage);
    }
  };

  const handleClose = () => {
    onClose();
  };

  const handleFillAll = async () => {
    if (!wordPhrase.trim()) return;

    setIsImproving(true);
    try {
      const result = await improveVocabularyItem(wordPhrase.trim(), true);
      setTranslation(result.translation || '');
      setExamplePhrase(result.example_phrase);
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to improve vocabulary item';
      setError(errorMessage);
    } finally {
      setIsImproving(false);
    }
  };

  const handleFillExample = async () => {
    if (!wordPhrase.trim()) return;

    setIsImproving(true);
    try {
      const result = await improveVocabularyItem(wordPhrase.trim(), false);
      setExamplePhrase(result.example_phrase);
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to improve vocabulary item';
      setError(errorMessage);
    } finally {
      setIsImproving(false);
    }
  };

  return (
    <Modal
      open={open}
      onClose={handleClose}
      aria-labelledby="edit-vocabulary-modal"
      aria-describedby="edit-vocabulary-modal-description"
    >
      <Box
        sx={{
          position: 'absolute',
          top: '50%',
          left: '50%',
          transform: 'translate(-50%, -50%)',
          width: { xs: '90%', sm: 500 },
          bgcolor: '#1f2937',
          border: '1px solid #374151',
          borderRadius: '0.5rem',
          boxShadow: 24,
          p: 4,
          color: 'white',
        }}
      >
        <Box
          sx={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            mb: 3,
          }}
        >
          <Typography variant="h6" component="h2">
            {item ? 'Edit Vocabulary Item' : 'Add Vocabulary Item'}
          </Typography>
          <IconButton
            onClick={handleClose}
            sx={{ color: '#9ca3af', fontSize: '1.5rem' }}
          >
            ×
          </IconButton>
        </Box>

        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
          <TextField
            label="Swedish Word/Phrase"
            value={wordPhrase}
            onChange={(e) => setWordPhrase(e.target.value)}
            fullWidth
            variant="outlined"
            sx={{
              '& .MuiOutlinedInput-root': {
                color: 'white',
                '& fieldset': {
                  borderColor: '#374151',
                },
                '&:hover fieldset': {
                  borderColor: '#6b7280',
                },
                '&.Mui-focused fieldset': {
                  borderColor: 'var(--primary-color)',
                },
              },
              '& .MuiInputLabel-root': {
                color: '#9ca3af',
                '&.Mui-focused': {
                  color: 'var(--primary-color)',
                },
              },
            }}
          />

          <Box sx={{ display: 'flex', gap: 1, justifyContent: 'center' }}>
            <CustomButton
              variant="secondary"
              onClick={handleFillAll}
              disabled={!wordPhrase.trim() || isImproving}
              size="small"
            >
              Fill All
            </CustomButton>
            <CustomButton
              variant="secondary"
              onClick={handleFillExample}
              disabled={!wordPhrase.trim() || isImproving}
              size="small"
            >
              Fill Example
            </CustomButton>
          </Box>

          <TextField
            label="English Translation"
            value={translation}
            onChange={(e) => setTranslation(e.target.value)}
            fullWidth
            variant="outlined"
            sx={{
              '& .MuiOutlinedInput-root': {
                color: 'white',
                '& fieldset': {
                  borderColor: '#374151',
                },
                '&:hover fieldset': {
                  borderColor: '#6b7280',
                },
                '&.Mui-focused fieldset': {
                  borderColor: 'var(--primary-color)',
                },
              },
              '& .MuiInputLabel-root': {
                color: '#9ca3af',
                '&.Mui-focused': {
                  color: 'var(--primary-color)',
                },
              },
            }}
          />

          <TextField
            label="Example Phrase (Optional)"
            value={examplePhrase}
            onChange={(e) => setExamplePhrase(e.target.value)}
            fullWidth
            variant="outlined"
            multiline
            rows={2}
            sx={{
              '& .MuiOutlinedInput-root': {
                color: 'white',
                '& fieldset': {
                  borderColor: '#374151',
                },
                '&:hover fieldset': {
                  borderColor: '#6b7280',
                },
                '&.Mui-focused fieldset': {
                  borderColor: 'var(--primary-color)',
                },
              },
              '& .MuiInputLabel-root': {
                color: '#9ca3af',
                '&.Mui-focused': {
                  color: 'var(--primary-color)',
                },
              },
            }}
          />

          <Box sx={{ display: 'flex', alignItems: 'center' }}>
            <StyledCheckbox
              checked={inLearn}
              onChange={setInLearn}
              label="In Learning"
            />
          </Box>

          {error && (
            <Typography sx={{ color: '#ef4444', fontSize: '0.875rem', mt: 1 }}>
              {error}
            </Typography>
          )}

          <Box sx={{ display: 'flex', gap: 2, justifyContent: 'space-between', mt: 2 }}>
            {item && onDelete && (
              <CustomButton
                variant="secondary"
                onClick={onDelete}
                sx={{
                  color: '#ef4444',
                  '&:hover': {
                    color: '#dc2626',
                    backgroundColor: 'rgba(239, 68, 68, 0.1)',
                  },
                }}
              >
                Delete
              </CustomButton>
            )}
            <Box sx={{ display: 'flex', gap: 2 }}>
              <CustomButton variant="secondary" onClick={handleClose}>
                Cancel
              </CustomButton>
              <CustomButton
                variant="save"
                onClick={handleSave}
                disabled={!wordPhrase.trim() || !translation.trim()}
              >
                {item ? 'Save Changes' : 'Add Item'}
              </CustomButton>
            </Box>
          </Box>
        </Box>
      </Box>
    </Modal>
  );
};

export default AddEditVocabularyModal;