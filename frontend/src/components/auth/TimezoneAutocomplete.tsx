import React, { useMemo } from "react";
import { Autocomplete, Box, TextField } from "@mui/material";
import type { SxProps, Theme } from "@mui/material";

interface TimezoneAutocompleteProps {
  label: string;
  value: string;
  onChange: (value: string) => void;
  error?: boolean;
  helperText?: string;
  sx?: SxProps<Theme>;
}

// eslint-disable-next-line react-refresh/only-export-components
export const isValidTimezone = (value: string): boolean => {
  const trimmed = value.trim();
  if (trimmed === "UTC") {
    return true;
  }
  if (!trimmed.includes("/")) {
    return false;
  }

  try {
    new Intl.DateTimeFormat("en-US", { timeZone: trimmed }).format();
    return true;
  } catch {
    return false;
  }
};

// eslint-disable-next-line react-refresh/only-export-components
export const getTimezoneOptions = (
  savedTimezone: string,
  detectedTimezone?: string
): string[] => {
  const options = new Set<string>(["UTC"]);
  const supportedValuesOf = Intl.supportedValuesOf;
  if (typeof supportedValuesOf === "function") {
    try {
      for (const timezone of supportedValuesOf("timeZone")) {
        if (isValidTimezone(timezone)) {
          options.add(timezone);
        }
      }
    } catch {
      // Keep the small UTC/saved/detected fallback if the browser API is unavailable.
    }
  }

  for (const timezone of [savedTimezone, detectedTimezone ?? ""]) {
    if (isValidTimezone(timezone)) {
      options.add(timezone.trim());
    }
  }

  return Array.from(options).sort((left, right) => {
    if (left === "UTC") return -1;
    if (right === "UTC") return 1;
    return left.localeCompare(right);
  });
};

const detectTimezone = (): string | undefined => {
  try {
    return Intl.DateTimeFormat().resolvedOptions().timeZone;
  } catch {
    return undefined;
  }
};

const TimezoneAutocomplete: React.FC<TimezoneAutocompleteProps> = ({
  label,
  value,
  onChange,
  error = false,
  helperText,
  sx = {},
}) => {
  const detectedTimezone = useMemo(detectTimezone, []);
  const options = useMemo(
    () => getTimezoneOptions(value, detectedTimezone),
    [value, detectedTimezone]
  );
  const selectedValue = options.includes(value) ? value : options[0] ?? "UTC";

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
      options={options}
      value={selectedValue}
      disableClearable
      autoHighlight
      onChange={(_event, newValue) => {
        if (typeof newValue === "string") {
          onChange(newValue);
        }
      }}
      renderInput={(params) => (
        <TextField
          {...params}
          name="timezone"
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

export default TimezoneAutocomplete;
