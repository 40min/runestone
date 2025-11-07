import React, { useState } from "react";
import type { FormEvent } from "react";
import { Box, Snackbar, Alert } from "@mui/material";
import type { AlertColor } from "@mui/material";
import { useAuthActions } from "../../hooks/useAuth";
import { CustomButton } from "../ui";
import AuthButton from "./AuthButton";
import AuthTextField from "./AuthTextField";

interface RegisterProps {
  onSwitchToLogin: () => void;
}

const Register: React.FC<RegisterProps> = ({ onSwitchToLogin }) => {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [name, setName] = useState("");
  const [surname, setSurname] = useState("");
  const [snackbar, setSnackbar] = useState<{
    open: boolean;
    message: string;
    severity: AlertColor;
  }>({
    open: false,
    message: "",
    severity: "error",
  });
  const { register, loading } = useAuthActions();

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();

    if (password !== confirmPassword) {
      setSnackbar({
        open: true,
        message: "Passwords do not match",
        severity: "error",
      });
      return;
    }

    if (password.length < 6) {
      setSnackbar({
        open: true,
        message: "Password must be at least 6 characters",
        severity: "error",
      });
      return;
    }

    try {
      await register({
        email,
        password,
        name: name || undefined,
        surname: surname || undefined,
      });
    } catch (err) {
      const errorMessage =
        err instanceof Error ? err.message : "An error occurred";

      // Log technical details to console
      console.error("Registration error:", err);

      setSnackbar({
        open: true,
        message: errorMessage,
        severity: "error",
      });
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
        Register
      </h2>

      <AuthTextField
        label="Email"
        name="email"
        type="email"
        value={email}
        onChange={(e) => setEmail(e.target.value)}
        required
        autoComplete="email"
        autoFocus
      />

      <AuthTextField
        label="Password (min. 6 characters)"
        name="password"
        type="password"
        value={password}
        onChange={(e) => setPassword(e.target.value)}
        required
        autoComplete="new-password"
      />

      <AuthTextField
        label="Confirm Password"
        name="confirmPassword"
        type="password"
        value={confirmPassword}
        onChange={(e) => setConfirmPassword(e.target.value)}
        required
        autoComplete="new-password"
      />

      <AuthTextField
        label="Name (optional)"
        name="name"
        value={name}
        onChange={(e) => setName(e.target.value)}
      />

      <AuthTextField
        label="Surname (optional)"
        name="surname"
        value={surname}
        onChange={(e) => setSurname(e.target.value)}
      />

      <AuthButton
        type="submit"
        loading={loading}
        loadingText="Registering..."
        onClick={(e) => {
          e.preventDefault();
          handleSubmit(e);
        }}
      >
        Register
      </AuthButton>

      <CustomButton
        onClick={onSwitchToLogin}
        variant="secondary"
        sx={{ mt: 1 }}
      >
        Already have an account? Login
      </CustomButton>

      <Snackbar
        open={snackbar.open}
        autoHideDuration={6000}
        onClose={() => setSnackbar({ ...snackbar, open: false })}
        anchorOrigin={{ vertical: "bottom", horizontal: "center" }}
      >
        <Alert
          onClose={() => setSnackbar({ ...snackbar, open: false })}
          severity={snackbar.severity}
          sx={{ width: "100%" }}
        >
          {snackbar.message}
        </Alert>
      </Snackbar>
    </Box>
  );
};

export default Register;
