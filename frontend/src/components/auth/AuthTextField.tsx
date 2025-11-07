import React from "react";
import { TextField } from "@mui/material";

interface AuthTextFieldProps {
  label: string;
  name: string;
  type?: string;
  value: string;
  onChange: (e: React.ChangeEvent<HTMLInputElement>) => void;
  required?: boolean;
  autoComplete?: string;
  autoFocus?: boolean;
  error?: boolean;
  helperText?: string;
}

const AuthTextField: React.FC<AuthTextFieldProps> = ({
  label,
  name,
  type = "text",
  value,
  onChange,
  required = false,
  autoComplete,
  autoFocus = false,
  error = false,
  helperText,
}) => {
  return (
    <TextField
      label={label}
      name={name}
      type={type}
      value={value}
      onChange={onChange}
      required={required}
      fullWidth
      autoComplete={autoComplete}
      autoFocus={autoFocus}
      error={error}
      helperText={helperText}
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
      }}
    />
  );
};

export default AuthTextField;
