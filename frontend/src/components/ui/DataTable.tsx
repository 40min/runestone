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
  const allSelected = data.length > 0 && data.every((row) => selectedItems.get(row.id));
  const someSelected = data.some((row) => selectedItems.get(row.id)) && !allSelected;

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
