import React from 'react';
import {
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper,
  Box,
  Typography,
  useTheme,
  useMediaQuery,
} from '@mui/material';
import type { SxProps, Theme } from '@mui/material';
import StyledCheckbox from './StyledCheckbox';

interface Column<T> {
  key: keyof T | string;
  label: string;
  render?: (value: unknown, row: T, index: number) => React.ReactNode;
  sx?: SxProps<Theme>;
}

interface DataTableProps<T extends { id: string }> {
  columns: Column<T>[];
  data: T[];
  selectable?: boolean;
  selectedItems?: Map<string, boolean>;
  onSelectionChange?: (id: string, checked: boolean) => void;
  onSelectAll?: (checked: boolean) => void;
  onRowClick?: (row: T, index: number) => void;
  masterCheckboxId?: string;
  rowCheckboxIdPrefix?: string;
  sx?: SxProps<Theme>;
}

function DataTable<T extends { id: string } & Record<string, unknown>>({
  columns,
  data,
  selectable = false,
  selectedItems = new Map(),
  onSelectionChange,
  onSelectAll,
  onRowClick,
  masterCheckboxId,
  rowCheckboxIdPrefix,
  sx = {},
}: DataTableProps<T>) {
  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down('sm'));
  const allSelected = data.length > 0 && data.every((row) => selectedItems.get(row.id));
  const someSelected = data.some((row) => selectedItems.get(row.id)) && !allSelected;

  const handleSelectAll = (checked: boolean) => {
    if (onSelectAll) {
      onSelectAll(checked);
    }
  };

  if (isMobile) {
    return (
      <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2, ...sx }}>
         {selectable && (
          <Box sx={{
            display: 'flex',
            alignItems: 'center',
            mb: 1,
            p: 1.5,
            backgroundColor: '#2a1f35',
            borderRadius: '0.5rem',
            border: '1px solid #4d3c63'
          }}>
             <StyledCheckbox
              id={masterCheckboxId}
              checked={allSelected}
              indeterminate={someSelected}
              onChange={handleSelectAll}
            />
            <Typography sx={{ ml: 1, color: 'white', fontWeight: 'bold' }}>
              Select All
            </Typography>
          </Box>
        )}
        {data.map((row, index) => (
          <Paper
            key={row.id}
            elevation={0}
            onClick={() => onRowClick?.(row, index)}
            sx={{
              backgroundColor: '#2a1f35',
              border: '1px solid #4d3c63',
              borderRadius: '0.5rem',
              p: 2,
              cursor: onRowClick ? 'pointer' : 'default',
              '&:hover': {
                backgroundColor: onRowClick ? 'rgba(255, 255, 255, 0.05)' : '#2a1f35',
              },
              position: 'relative',
              display: 'flex',
              flexDirection: 'column',
              gap: 1.5,
            }}
          >
             {selectable && (
               <Box sx={{
                 position: 'absolute',
                 top: 12,
                 right: 12,
                 zIndex: 1
               }}
               onClick={(e) => e.stopPropagation()} // Prevent row click when clicking checkbox
               >
                  <StyledCheckbox
                    id={rowCheckboxIdPrefix ? `${rowCheckboxIdPrefix}-${row.id}` : undefined}
                    checked={selectedItems.get(row.id) || false}
                    onChange={(checked) => onSelectionChange?.(row.id, checked)}
                  />
               </Box>
            )}

            {columns.map((column) => {
              const value = row[column.key as keyof T];
              return (
                <Box key={String(column.key)} sx={{ display: 'flex', flexDirection: 'column', gap: 0.5 }}>
                  <Typography
                    variant="caption"
                    sx={{
                      color: '#9ca3af',
                      textTransform: 'uppercase',
                      fontWeight: 'bold',
                      fontSize: '0.7rem'
                    }}
                  >
                    {column.label}
                  </Typography>
                  <Box sx={{
                    color: 'white',
                    wordBreak: 'break-word',
                    // Apply column specific styles if present, but ignore width percentages that might break mobile layout
                    ...column.sx
                  }}>
                     {column.render ? column.render(value, row, index) : String(value || '—')}
                  </Box>
                </Box>
              );
            })}
          </Paper>
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
            {selectable && (
              <TableCell
                sx={{
                  color: 'white',
                  fontWeight: 'bold',
                  borderBottom: '1px solid #4d3c63',
                  width: '48px', // Fixed width for checkbox column
                }}
              >
                <StyledCheckbox
                  id={masterCheckboxId}
                  checked={allSelected}
                  indeterminate={someSelected}
                  onChange={handleSelectAll}
                />
              </TableCell>
            )}
            {columns.map((column) => (
              <TableCell
                key={String(column.key)}
                sx={{
                  color: 'white',
                  fontWeight: 'bold',
                  borderBottom: '1px solid #4d3c63',
                  ...column.sx,
                }}
              >
                {column.label}
              </TableCell>
            ))}
          </TableRow>
        </TableHead>
        <TableBody>
          {data.map((row, index) => (
            <TableRow
              key={row.id} // Use row.id as key
              sx={{
                borderBottom: '1px solid #4d3c63',
                cursor: onRowClick ? 'pointer' : 'default',
                '&:hover': {
                  backgroundColor: onRowClick ? 'rgba(255, 255, 255, 0.05)' : 'transparent',
                },
              }}
              onClick={() => onRowClick?.(row, index)}
            >
              {selectable && (
                <TableCell sx={{ borderBottom: '1px solid #4d3c63' }}>
                  <StyledCheckbox
                    id={rowCheckboxIdPrefix ? `${rowCheckboxIdPrefix}-${row.id}` : undefined} // Use row.id for checkbox ID
                    checked={selectedItems.get(row.id) || false} // Check against map
                    onChange={(checked) => onSelectionChange?.(row.id, checked)} // Pass row.id
                  />
                </TableCell>
              )}
              {columns.map((column) => {
                const value = row[column.key as keyof T];
                return (
                  <TableCell
                    key={String(column.key)}
                    sx={{
                      color: column.key === 'english' || column.key === 'translation' || column.key === 'example_phrase' || column.key === 'saved'
                        ? '#9ca3af'
                        : 'white',
                      borderBottom: '1px solid #4d3c63',
                      ...column.sx,
                    }}
                  >
                    {column.render ? column.render(value, row, index) : String(value || '—')}
                  </TableCell>
                );
              })}
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </TableContainer>
  );
}

export default DataTable;
