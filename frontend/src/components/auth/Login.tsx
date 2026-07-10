import React, { useState } from "react";
import type { FormEvent } from "react";
import { Snackbar, Alert } from "@mui/material";
import type { AlertColor } from "@mui/material";
import { Mail, Lock, ShieldCheck } from "lucide-react";
import { useAuthActions } from "../../hooks/useAuth";
import AuthButton from "./AuthButton";
import AuthTextField from "./AuthTextField";
import AuthLayout from "./AuthLayout";

interface LoginProps {
  onSwitchToRegister?: () => void;
}

const Login: React.FC<LoginProps> = ({ onSwitchToRegister }) => {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [snackbar, setSnackbar] = useState<{
    open: boolean;
    message: string;
    severity: AlertColor;
  }>({
    open: false,
    message: "",
    severity: "error",
  });
  const { login, loading } = useAuthActions();

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();

    try {
      await login({ email, password });
    } catch (err) {
      const errorMessage =
        err instanceof Error ? err.message : "An error occurred";

      // Log technical details to console
      console.error("Login error:", err);

      setSnackbar({ open: true, message: errorMessage, severity: "error" });
    }
  };

  return (
    <AuthLayout>
      <form onSubmit={handleSubmit} className="auth-form">
        {/* Heading */}
        <h2 id="login-heading" className="auth-form-title">
          Login
        </h2>
        <p className="auth-form-subtitle">
          Enter your credentials to access your account.
        </p>

        {/* Fields */}
        <AuthTextField
          label="Email"
          name="email"
          type="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          required
          autoComplete="email"
          autoFocus
          startIcon={<Mail size={16} />}
        />

        <AuthTextField
          label="Password"
          name="password"
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          required
          autoComplete="current-password"
          startIcon={<Lock size={16} />}
        />

        {/* Submit */}
        <AuthButton
          type="submit"
          loading={loading}
          loadingText="Logging in..."
        >
          Login
        </AuthButton>

        {/* Switch to register */}
        <p className="auth-switch-text">
          Don&apos;t have an account?{" "}
          <button
            type="button"
            className="auth-switch-link auth-switch-highlight"
            onClick={onSwitchToRegister}
          >
            Register
          </button>
        </p>

        {/* Security note */}
        <div className="auth-security-note">
          <ShieldCheck size={20} className="auth-security-icon" />
          <span>
            Your data is encrypted and secure.
            <br />
            We never share your information.
          </span>
        </div>
      </form>

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
    </AuthLayout>
  );
};

export default Login;
