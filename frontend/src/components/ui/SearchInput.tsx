import React from 'react';
import { Box, TextField } from '@mui/material';
import type { SxProps, Theme } from '@mui/material';
import CustomButton from './CustomButton';

interface SearchInputProps {
  value: string;
  onChange: (e: React.ChangeEvent<HTMLInputElement>) => void;
  placeholder?: string;
  fullWidth?: boolean;
  sx?: SxProps<Theme>;
  onSearch?: () => void;
}

const SearchInput: React.FC<SearchInputProps> = ({
  value,
  onChange,
  placeholder = "Search...",
  fullWidth = true,
  sx = {},
  onSearch,
}) => {
  return (
    <Box sx={{ mb: 4, maxWidth: 400, display: 'flex', alignItems: 'center', ...sx }}>
      <TextField
        fullWidth={fullWidth}
        variant="outlined"
        placeholder={placeholder}
        value={value}
        onChange={onChange}
        sx={{
          "& .MuiOutlinedInput-root": {
            backgroundColor: "#1f2937",
            color: "white",
            "& fieldset": {
              borderColor: "#374151",
            },
            "&:hover fieldset": {
              borderColor: "#4b5563",
            },
            "&.Mui-focused fieldset": {
              borderColor: "#60a5fa",
            },
          },
          "& .MuiInputBase-input::placeholder": {
            color: "#9ca3af",
          },
        }}
      />
      {onSearch && (
        <CustomButton variant="primary" onClick={onSearch} sx={{ ml: 1 }}>
          Search
        </CustomButton>
      )}
    </Box>
  );
};

export default SearchInput;