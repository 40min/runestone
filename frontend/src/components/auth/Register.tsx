import React, { useState } from "react";
import type { FormEvent } from "react";
import { Snackbar, Alert } from "@mui/material";
import type { AlertColor } from "@mui/material";
import { Mail, Lock, User, ShieldCheck, UserPlus } from "lucide-react";
import { useAuthActions } from "../../hooks/useAuth";
import { CustomButton } from "../ui";
import AuthButton from "./AuthButton";
import AuthTextField from "./AuthTextField";
import AuthLayout from "./AuthLayout";

interface RegisterProps {
  onSwitchToLogin: () => void;
}

const Register: React.FC<RegisterProps> = ({ onSwitchToLogin }) => {
  const [isRegistered, setIsRegistered] = useState(false);
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
      setIsRegistered(true);
    } catch (err) {
      const errorMessage =
        err instanceof Error ? err.message : "An error occurred";

      console.error("Registration error:", err);

      setSnackbar({
        open: true,
        message: errorMessage,
        severity: "error",
      });
    }
  };

  if (isRegistered) {
    return (
      <AuthLayout
        headline="A new rune awaits"
        tagline="Carve your name. Begin the journey."
      >
        <div
          className="auth-form text-center"
          role="region"
          aria-labelledby="register-success-heading"
        >
          <h2 id="register-success-heading" className="auth-form-title">
            Registered!
          </h2>
          <p className="auth-form-subtitle">
            Your account has been created, but it needs to be activated by an
            administrator before you can log in.
          </p>
          <CustomButton onClick={onSwitchToLogin} variant="primary" sx={{ mt: 2 }}>
            Return to Login
          </CustomButton>
        </div>
      </AuthLayout>
    );
  }

  return (
    <AuthLayout
      headline="A new rune awaits"
      tagline="Carve your name. Begin the journey."
    >
      <form
        onSubmit={handleSubmit}
        className="auth-form"
        aria-labelledby="register-heading"
      >
        {/* Icon + Heading */}
        <div className="auth-register-icon-wrap">
          <UserPlus size={32} className="auth-register-icon" />
        </div>

        <div>
          <h2 id="register-heading" className="auth-form-title text-center">
            Create Your Account
          </h2>
          <p className="auth-form-subtitle text-center">
            Join Runestone and start learning smarter.
          </p>
        </div>

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
          placeholder="you@example.com"
        />

        <AuthTextField
          label="Password"
          name="password"
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          required
          autoComplete="new-password"
          startIcon={<Lock size={16} />}
          placeholder="Min. 6 characters"
        />

        <AuthTextField
          label="Confirm Password"
          name="confirmPassword"
          type="password"
          value={confirmPassword}
          onChange={(e) => setConfirmPassword(e.target.value)}
          required
          autoComplete="new-password"
          startIcon={<Lock size={16} />}
          placeholder="Re-enter your password"
        />

        <AuthTextField
          label="First Name (optional)"
          name="name"
          value={name}
          onChange={(e) => setName(e.target.value)}
          startIcon={<User size={16} />}
          placeholder="Your first name"
        />

        <AuthTextField
          label="Last Name (optional)"
          name="surname"
          value={surname}
          onChange={(e) => setSurname(e.target.value)}
          startIcon={<User size={16} />}
          placeholder="Your last name"
        />

        {/* Submit */}
        <AuthButton type="submit" loading={loading} loadingText="Registering...">
          Register
        </AuthButton>

        {/* Security note */}
        <div className="auth-security-note">
          <ShieldCheck size={20} className="auth-security-icon" />
          <span>
            We respect your privacy.
            <br />
            Your data is{" "}
            <span className="text-[var(--primary-color)]">secure</span> and
            never shared.
          </span>
        </div>

        {/* Switch to login */}
        <p className="auth-switch-text">
          Already have an account?{" "}
          <button
            type="button"
            className="auth-switch-link auth-switch-highlight"
            onClick={onSwitchToLogin}
          >
            Login
          </button>
        </p>
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

export default Register;
