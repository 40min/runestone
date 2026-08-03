import React from "react";
import { Autocomplete, TextField, Box } from "@mui/material";
import type { SxProps, Theme } from "@mui/material";
import { LANGUAGES } from "../../constants";

interface LanguageAutocompleteProps {
  label: string;
  value: string;
  onChange: (value: string) => void;
  error?: boolean;
  helperText?: string;
  sx?: SxProps<Theme>;
}

const LanguageAutocomplete: React.FC<LanguageAutocompleteProps> = ({
  label,
  value,
  onChange,
  error = false,
  helperText,
  sx = {},
}) => {
  const defaultSx = {
    "& .MuiOutlinedInput-root": {
      color: "white",
      "& fieldset": { borderColor: "rgba(255, 255, 255, 0.3)" },
      "&:hover fieldset": { borderColor: "rgba(255, 255, 255, 0.5)" },
      "&.Mui-focused fieldset": {
        borderColor: "rgba(255, 255, 255, 0.8)",
      },
    },
    "& .MuiInputLabel-root": { color: "rgba(255, 255, 255, 0.7)" },
    "& .MuiInputLabel-root.Mui-focused": { color: "white" },
    "& .MuiAutocomplete-endAdornment .MuiIconButton-root": {
      color: "rgba(255, 255, 255, 0.7)",
    },
  };

  return (
    <Autocomplete
      options={LANGUAGES}
      value={value || null}
      onInputChange={(_event, newInputValue) => {
        onChange(newInputValue || "");
      }}
      freeSolo
      renderInput={(params) => (
        <TextField
          {...params}
          label={label}
          error={error}
          helperText={helperText}
          fullWidth
          sx={[defaultSx, ...(Array.isArray(sx) ? sx : [sx])]}
        />
      )}
      PaperComponent={({ children }) => (
        <Box
          sx={{
            backgroundColor: "#0d1534",
            border: "1px solid rgba(99, 114, 173, 0.35)",
            color: "white",
            fontFamily: "inherit",
            "& .MuiAutocomplete-option": {
              "&:hover": {
                backgroundColor: "rgba(148, 163, 184, 0.08)",
              },
              '&[aria-selected="true"]': {
                backgroundColor: "rgba(56, 224, 123, 0.12)",
              },
            },
          }}
        >
          {children}
        </Box>
      )}
    />
  );
};

export default LanguageAutocomplete;
