import React from 'react';
import ClearIcon from '@mui/icons-material/Clear';
import { Box, IconButton, InputAdornment, TextField } from '@mui/material';
import type { SxProps, Theme } from '@mui/material';
import CustomButton from './CustomButton';

interface SearchInputProps {
  value: string;
  onChange: (e: React.ChangeEvent<HTMLInputElement>) => void;
  placeholder?: string;
  fullWidth?: boolean;
  sx?: SxProps<Theme>;
  onSearch?: () => void;
  onClear?: () => void;
  clearLabel?: string;
}

const SearchInput: React.FC<SearchInputProps> = ({
  value,
  onChange,
  placeholder = "Search...",
  fullWidth = true,
  sx = {},
  onSearch,
  onClear,
  clearLabel = "Clear search",
}) => {
  const showClearButton = Boolean(onClear && value);
  const handleKeyDown = (event: React.KeyboardEvent<HTMLInputElement>) => {
    if (event.key === "Enter" && onSearch) {
      event.preventDefault();
      onSearch();
    }
  };

  return (
    <Box sx={{ mb: 4, maxWidth: 400, display: 'flex', alignItems: 'center', ...sx }}>
      <TextField
        fullWidth={fullWidth}
        variant="outlined"
        placeholder={placeholder}
        value={value}
        onChange={onChange}
        onKeyDown={handleKeyDown}
        slotProps={{
          input: {
            endAdornment: showClearButton ? (
              <InputAdornment position="end">
                <IconButton
                  aria-label={clearLabel}
                  edge="end"
                  onClick={onClear}
                  size="small"
                  sx={{ color: "#9ca3af" }}
                >
                  <ClearIcon fontSize="small" />
                </IconButton>
              </InputAdornment>
            ) : undefined,
          },
        }}
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
