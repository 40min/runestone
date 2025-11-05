import React, { useState } from "react";
import type { FormEvent } from "react";
import { Box, TextField } from "@mui/material";
import { useAuthActions } from "../../hooks/useAuth";

const Login: React.FC = () => {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [localError, setLocalError] = useState("");
  const { login, loading, error } = useAuthActions();

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setLocalError("");

    if (password.length < 6) {
      setLocalError("Password must be at least 6 characters");
      return;
    }

    try {
      await login({ email, password });
    } catch {
      // Error is handled by the hook
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

      {(error || localError) && (
        <Box
          sx={{
            p: 2,
            backgroundColor: "rgba(211, 47, 47, 0.1)",
            border: "1px solid rgba(211, 47, 47, 0.5)",
            borderRadius: 1,
            color: "#f44336",
          }}
        >
          {error || localError}
        </Box>
      )}

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

      <Box
        component="button"
        type="submit"
        onClick={(e) => {
          e.preventDefault();
          handleSubmit(e);
        }}
        disabled={loading}
        sx={{
          mt: 2,
          padding: '10px 20px',
          backgroundColor: 'var(--primary-color)',
          color: 'white',
          border: 'none',
          borderRadius: '6px',
          cursor: loading ? 'not-allowed' : 'pointer',
          fontSize: '14px',
          fontWeight: 'bold',
          opacity: loading ? 0.6 : 1,
          '&:hover': {
            opacity: 0.9,
          },
        }}
      >
        {loading ? "Logging in..." : "Login"}
      </Box>
    </Box>
  );
};

export default Login;
