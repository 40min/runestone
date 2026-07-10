import React, { useState } from "react";
import { TextField, InputAdornment, IconButton } from "@mui/material";
import { Eye, EyeOff } from "lucide-react";

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
  /** Optional leading icon rendered inside the input. */
  startIcon?: React.ReactNode;
  /** Placeholder text shown inside the input when empty. */
  placeholder?: string;
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
  startIcon,
  placeholder,
}) => {
  const isPassword = type === "password";
  const [showPassword, setShowPassword] = useState(false);

  const resolvedType = isPassword ? (showPassword ? "text" : "password") : type;

  return (
    <TextField
      label={label}
      name={name}
      type={resolvedType}
      value={value}
      onChange={onChange}
      required={required}
      fullWidth
      autoComplete={autoComplete}
      autoFocus={autoFocus}
      placeholder={placeholder}
      error={error}
      helperText={helperText}
      slotProps={{
        input: {
          startAdornment: startIcon ? (
            <InputAdornment position="start" sx={{ color: "rgba(255,255,255,0.4)", mr: 0.5 }}>
              {startIcon}
            </InputAdornment>
          ) : undefined,
          endAdornment: isPassword ? (
            <InputAdornment position="end">
              <IconButton
                aria-label={showPassword ? "Hide password" : "Show password"}
                onClick={() => setShowPassword((v) => !v)}
                edge="end"
                size="small"
                sx={{ color: "rgba(255,255,255,0.4)", "&:hover": { color: "rgba(255,255,255,0.8)" } }}
              >
                {showPassword ? <EyeOff size={18} /> : <Eye size={18} />}
              </IconButton>
            </InputAdornment>
          ) : undefined,
        },
      }}
      sx={{
        "& .MuiOutlinedInput-root": {
          color: "white",
          backgroundColor: "rgba(255,255,255,0.05)",
          borderRadius: "10px",
          "& fieldset": { borderColor: "rgba(255,255,255,0.15)" },
          "&:hover fieldset": { borderColor: "rgba(255,255,255,0.35)" },
          "&.Mui-focused fieldset": { borderColor: "rgba(56,224,123,0.6)", borderWidth: "1.5px" },
        },
        "& .MuiInputLabel-root": { color: "rgba(255,255,255,0.55)" },
        "& .MuiInputLabel-root.Mui-focused": { color: "rgba(56,224,123,0.9)" },
      }}
    />
  );
};

export default AuthTextField;
