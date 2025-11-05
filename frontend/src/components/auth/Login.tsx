import React, { useState } from "react";
import type { FormEvent } from "react";
import { Box, TextField } from "@mui/material";
import { useAuthActions } from "../../hooks/useAuth";
import { CustomButton, ErrorAlert } from "../ui";
import AuthButton from "./AuthButton";

interface LoginProps {
  onSwitchToRegister?: () => void;
}

const Login: React.FC<LoginProps> = ({ onSwitchToRegister }) => {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const { login, loading } = useAuthActions();

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError("");

    if (password.length < 6) {
      setError("Password must be at least 6 characters");
      return;
    }

    try {
      await login({ email, password });
    } catch (err) {
      setError(err instanceof Error ? err.message : "An error occurred");
    }
  };

  return (
    <Box
      component="form"
      onSubmit={handleSubmit}
      sx={{
        display: "flex",
        flexDirection: "column",
        gap: 2,
        maxWidth: 400,
        mx: "auto",
        mt: 8,
        p: 4,
        backgroundColor: "rgba(255, 255, 255, 0.05)",
        borderRadius: 2,
        backdropFilter: "blur(10px)",
      }}
    >
      <h2 className="text-3xl font-bold text-white text-center mb-4">
        Login
      </h2>

      {error && <ErrorAlert message={error} />}

      <TextField
        label="Email"
        type="email"
        value={email}
        onChange={(e) => setEmail(e.target.value)}
        required
        fullWidth
        sx={{
          "& .MuiOutlinedInput-root": {
            color: "white",
            "& fieldset": { borderColor: "rgba(255, 255, 255, 0.3)" },
            "&:hover fieldset": { borderColor: "rgba(255, 255, 255, 0.5)" },
            "&.Mui-focused fieldset": { borderColor: "rgba(255, 255, 255, 0.8)" },
          },
          "& .MuiInputLabel-root": { color: "rgba(255, 255, 255, 0.7)" },
          "& .MuiInputLabel-root.Mui-focused": { color: "white" },
        }}
      />

      <TextField
        label="Password"
        type="password"
        value={password}
        onChange={(e) => setPassword(e.target.value)}
        required
        fullWidth
        sx={{
          "& .MuiOutlinedInput-root": {
            color: "white",
            "& fieldset": { borderColor: "rgba(255, 255, 255, 0.3)" },
            "&:hover fieldset": { borderColor: "rgba(255, 255, 255, 0.5)" },
            "&.Mui-focused fieldset": { borderColor: "rgba(255, 255, 255, 0.8)" },
          },
          "& .MuiInputLabel-root": { color: "rgba(255, 255, 255, 0.7)" },
          "& .MuiInputLabel-root.Mui-focused": { color: "white" },
        }}
      />

      <AuthButton
        type="submit"
        loading={loading}
        loadingText="Logging in..."
        onClick={(e) => {
          e.preventDefault();
          handleSubmit(e);
        }}
      >
        Login
      </AuthButton>

      <CustomButton
        onClick={onSwitchToRegister}
        variant="secondary"
        sx={{ mt: 1 }}
      >
        Don't have an account? Register
      </CustomButton>
    </Box>
  );
};

export default Login;
