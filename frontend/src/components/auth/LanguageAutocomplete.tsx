import React from "react";
import { Autocomplete, TextField, Box } from "@mui/material";

interface LanguageAutocompleteProps {
  label: string;
  value: string;
  onChange: (value: string) => void;
  error?: boolean;
  helperText?: string;
}

const LANGUAGES = [
  "English",
  "Russian",
  "Spanish",
  "French",
  "German",
  "Italian",
  "Chinese",
  "Japanese",
  "Korean",
  "Portuguese",
  "Arabic",
  "Dutch",
  "Swedish",
  "Finnish",
  "Norwegian",
  "Danish",
  "Polish",
  "Turkish",
  "Vietnamese",
  "Hindi",
  "Bengali",
  "Urdu",
  "Czech",
  "Slovak",
  "Hungarian",
  "Romanian",
  "Greek",
  "Ukrainian",
  "Hebrew",
  "Indonesian",
  "Thai",
  "Malay",
  "Persian",
  "Bulgarian",
  "Croatian",
  "Serbian",
  "Slovenian",
  "Lithuanian",
  "Latvian",
  "Estonian",
];

const LanguageAutocomplete: React.FC<LanguageAutocompleteProps> = ({
  label,
  value,
  onChange,
  error = false,
  helperText,
}) => {
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
          sx={{
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
          }}
        />
      )}
      PaperComponent={({ children }) => (
        <Box
          sx={{
            backgroundColor: "#1e1e1e",
            color: "white",
            "& .MuiAutocomplete-option": {
              "&:hover": {
                backgroundColor: "rgba(255, 255, 255, 0.1)",
              },
              '&[aria-selected="true"]': {
                backgroundColor: "rgba(255, 255, 255, 0.2)",
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
