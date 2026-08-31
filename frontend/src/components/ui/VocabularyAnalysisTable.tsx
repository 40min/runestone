import React from 'react';
import {
  Box,
  Paper,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Typography,
  useMediaQuery,
  useTheme,
} from '@mui/material';
import type { SxProps, Theme } from '@mui/material';
import type { EnrichedVocabularyItem } from '../../hooks/useImageProcessing';
import StyledCheckbox from './StyledCheckbox';

interface VocabularyAnalysisTableProps {
  rows: EnrichedVocabularyItem[];
  selectedItems: Map<string, boolean>;
  onSelectionChange: (id: string, checked: boolean) => void;
  onSelectAll: (checked: boolean) => void;
  masterCheckboxId?: string;
  rowCheckboxIdPrefix?: string;
  sx?: SxProps<Theme>;
}

/**
 * Selection table for the analyzer's vocabulary results.
 * Desktop renders a bordered table; small screens render selectable cards.
 */
const VocabularyAnalysisTable: React.FC<VocabularyAnalysisTableProps> = ({
  rows,
  selectedItems,
  onSelectionChange,
  onSelectAll,
  masterCheckboxId,
  rowCheckboxIdPrefix,
  sx = {},
}) => {
  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down('sm'));
  const allSelected = rows.length > 0 && rows.every((row) => selectedItems.get(row.id));
  const someSelected = rows.some((row) => selectedItems.get(row.id)) && !allSelected;

  const rowCheckboxId = (row: EnrichedVocabularyItem) =>
    rowCheckboxIdPrefix ? `${rowCheckboxIdPrefix}-${row.id}` : undefined;

  if (isMobile) {
    return (
      <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1.25, ...sx }}>
        <Box
          sx={{
            display: 'flex',
            alignItems: 'center',
            p: 1.2,
            backgroundColor: 'rgba(34, 44, 95, 0.7)',
            border: '1px solid rgba(106, 121, 181, 0.5)',
            borderRadius: '0.65rem',
          }}
        >
          <StyledCheckbox
            id={masterCheckboxId}
            checked={allSelected}
            indeterminate={someSelected}
            onChange={onSelectAll}
          />
          <Typography sx={{ ml: 0.75, color: '#d8e2ff', fontWeight: 700 }}>
            Select All
          </Typography>
        </Box>
        {rows.map((row) => (
          <Box
            key={row.id}
            sx={{
              backgroundColor: 'rgba(20, 28, 74, 0.72)',
              border: '1px solid rgba(106, 120, 178, 0.4)',
              borderRadius: '0.9rem',
              p: 1.35,
              display: 'flex',
              alignItems: 'center',
              gap: 1.5,
            }}
          >
            <Box sx={{ display: 'flex', alignItems: 'center' }}>
              <StyledCheckbox
                id={rowCheckboxId(row)}
                checked={selectedItems.get(row.id) || false}
                onChange={(checked) => onSelectionChange(row.id, checked)}
              />
            </Box>
            <Box sx={{ minWidth: 0, flex: '0 0 30%' }}>
              <Typography
                sx={{
                  color: '#f4f7ff',
                  fontWeight: 700,
                  lineHeight: 1.25,
                  fontSize: '1.05rem',
                  wordBreak: 'break-word',
                }}
              >
                {row.swedish || '—'}
              </Typography>
              <Typography
                sx={{
                  color: '#adbce4',
                  fontSize: '0.95rem',
                  lineHeight: 1.2,
                  mt: 0.25,
                }}
              >
                {row.english || '—'}
              </Typography>
            </Box>
            <Typography
              sx={{
                color: '#d0d9ef',
                flex: 1,
                fontSize: '1rem',
                lineHeight: 1.3,
                whiteSpace: 'normal',
                wordBreak: 'break-word',
              }}
            >
              {row.example_phrase || '—'}
            </Typography>
          </Box>
        ))}
      </Box>
    );
  }

  return (
    <TableContainer
      component={Paper}
      sx={{
        backgroundColor: '#2a1f35',
        borderRadius: '0.5rem',
        ...sx,
      }}
    >
      <Table>
        <TableHead>
          <TableRow>
            <TableCell
              sx={{
                color: 'white',
                fontWeight: 'bold',
                borderBottom: '1px solid #4d3c63',
                width: '48px',
              }}
            >
              <StyledCheckbox
                id={masterCheckboxId}
                checked={allSelected}
                indeterminate={someSelected}
                onChange={onSelectAll}
              />
            </TableCell>
            {['Swedish', 'English', 'Example Phrase'].map((label) => (
              <TableCell
                key={label}
                sx={{
                  color: 'white',
                  fontWeight: 'bold',
                  borderBottom: '1px solid #4d3c63',
                }}
              >
                {label}
              </TableCell>
            ))}
          </TableRow>
        </TableHead>
        <TableBody>
          {rows.map((row) => (
            <TableRow key={row.id} sx={{ borderBottom: '1px solid #4d3c63' }}>
              <TableCell sx={{ borderBottom: '1px solid #4d3c63' }}>
                <StyledCheckbox
                  id={rowCheckboxId(row)}
                  checked={selectedItems.get(row.id) || false}
                  onChange={(checked) => onSelectionChange(row.id, checked)}
                />
              </TableCell>
              <TableCell
                sx={{ color: 'white', borderBottom: '1px solid #4d3c63' }}
              >
                {row.swedish || '—'}
              </TableCell>
              <TableCell
                sx={{ color: '#9ca3af', borderBottom: '1px solid #4d3c63' }}
              >
                {row.english || '—'}
              </TableCell>
              <TableCell
                sx={{ color: '#9ca3af', borderBottom: '1px solid #4d3c63' }}
              >
                {row.example_phrase || '—'}
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </TableContainer>
  );
};

export default VocabularyAnalysisTable;
