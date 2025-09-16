import React from 'react';
import {
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper,
} from '@mui/material';
import type { SxProps, Theme } from '@mui/material';
import StyledCheckbox from './StyledCheckbox';

interface Column<T> {
  key: keyof T | string;
  label: string;
  render?: (value: unknown, row: T, index: number) => React.ReactNode;
  sx?: SxProps<Theme>;
}

interface DataTableProps<T> {
  columns: Column<T>[];
  data: T[];
  selectable?: boolean;
  selectedItems?: boolean[];
  onSelectionChange?: (index: number, checked: boolean) => void;
  onSelectAll?: (checked: boolean) => void;
  onRowClick?: (row: T, index: number) => void;
  
  sx?: SxProps<Theme>;
}

function DataTable<T extends Record<string, unknown>>({
  columns,
  data,
  selectable = false,
  selectedItems = [],
  onSelectionChange,
  onSelectAll,
  onRowClick,

  sx = {},
}: DataTableProps<T>) {
  const allSelected = selectedItems.length > 0 && selectedItems.every(Boolean);
  const someSelected = selectedItems.some(Boolean) && !allSelected;

  const handleSelectAll = (checked: boolean) => {
    if (onSelectAll) {
      onSelectAll(checked);
    }
  };

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
                }}
              >
                <StyledCheckbox
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
              key={index}
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
                    checked={selectedItems[index] || false}
                    onChange={(checked) => onSelectionChange?.(index, checked)}
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