import React, { useState, useEffect } from "react";
import type { FormEvent } from "react";
import { Box, Typography } from "@mui/material";
import type { SxProps, Theme } from "@mui/material";
import { useAuth } from "../../context/AuthContext";
import { useAuthActions } from "../../hooks/useAuth";
import { ErrorAlert } from "../ui";
import AuthButton from "./AuthButton";
import AuthTextField from "./AuthTextField";
import LanguageAutocomplete from "./LanguageAutocomplete";

const profileFontFamily = '"Space Grotesk", "Noto Sans", sans-serif';

const profileFieldSx: SxProps<Theme> = {
  fontFamily: profileFontFamily,
  "& .MuiOutlinedInput-root": {
    color: "#f3f6ff",
    backgroundColor: "rgba(9, 15, 51, 0.55)",
    borderRadius: "0.75rem",
    fontFamily: profileFontFamily,
    "& fieldset": { borderColor: "rgba(99, 114, 173, 0.45)" },
    "&:hover fieldset": { borderColor: "rgba(99, 114, 173, 0.8)" },
    "&.Mui-focused fieldset": {
      borderColor: "#38e07b",
      borderWidth: "1.5px",
    },
  },
  "& .MuiInputBase-input": { fontFamily: profileFontFamily },
  "& .MuiInputLabel-root": {
    color: "#a8b6d8",
    fontFamily: profileFontFamily,
  },
  "& .MuiInputLabel-root.Mui-focused": {
    color: "#38e07b",
  },
  "& .MuiFormHelperText-root": {
    color: "#8ea0d0",
    fontFamily: profileFontFamily,
  },
};

const Profile: React.FC = () => {
  const { userData } = useAuth();
  const { updateProfile, refreshUserData, loading } = useAuthActions();
  const [formData, setFormData] = useState<{
    name: string;
    surname: string;
    telegram_username: string;
    mother_tongue: string;
    timezone: string;
    password: string;
    confirmPassword: string;
    email: string;
  }>({
    name: "",
    surname: "",
    telegram_username: "",
    mother_tongue: "",
    timezone: "UTC",
    password: "",
    confirmPassword: "",
    email: "",
  });
  const [successMessage, setSuccessMessage] = useState("");
  const [error, setError] = useState("");

  // Refresh user data on mount to get latest memory from agent
  useEffect(() => {
    refreshUserData();
    // Only run on mount
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (userData) {
      setFormData({
        name: userData.name || "",
        surname: userData.surname || "",
        telegram_username: userData.telegram_username || "",
        mother_tongue: userData.mother_tongue || "",
        timezone: userData.timezone || "UTC",
        password: "",
        confirmPassword: "",
        email: userData.email || "",
      });
    }
  }, [userData]);

  const handleChange = (field: string, value: string) => {
    setFormData((prev) => ({ ...prev, [field]: value }));
  };

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError("");
    setSuccessMessage("");

    if (!userData) {
      setError("User data not available");
      return;
    }

    if (formData.password && formData.password !== formData.confirmPassword) {
      setError("Passwords do not match");
      return;
    }

    if (formData.password && formData.password.length < 6) {
      setError("Password must be at least 6 characters");
      return;
    }

    try {
      const updateData: Record<string, string | null> = {
        name: formData.name || null,
        surname: formData.surname || null,
        telegram_username: formData.telegram_username || null,
        mother_tongue: formData.mother_tongue || null,
        timezone: formData.timezone,
      };

      if (formData.password) {
        updateData.password = formData.password;
      }

      if (formData.email && formData.email !== userData.email) {
        updateData.email = formData.email;
      }

      await updateProfile(updateData);
      setSuccessMessage("Profile updated successfully!");
      setFormData((prev) => ({
        ...prev,
        password: "",
        confirmPassword: "",
      }));
    } catch (err) {
      setError(err instanceof Error ? err.message : "An error occurred");
    }
  };

  if (!userData) {
    return null;
  }

  return (
    <Box
      component="form"
      onSubmit={handleSubmit}
      sx={{
        display: "flex",
        flexDirection: "column",
        gap: 2.25,
        maxWidth: 720,
        mx: "auto",
        py: { xs: 2, sm: 4 },
        px: { xs: 2, sm: 3 },
        background:
          "radial-gradient(circle at 12% 8%, rgba(35, 50, 116, 0.42), rgba(7, 12, 44, 0.97))",
        border: "1px solid rgba(99, 114, 173, 0.35)",
        borderRadius: "1rem",
        boxShadow: "inset 0 1px 0 rgba(255,255,255,0.04)",
        fontFamily: profileFontFamily,
      }}
    >
      <Typography
        component="h1"
        sx={{
          color: "#f3f6ff",
          fontFamily: profileFontFamily,
          fontSize: { xs: "2.5rem", sm: "3.25rem" },
          fontWeight: 700,
          letterSpacing: "-0.055em",
          lineHeight: 1,
          textAlign: "center",
          mb: 0.5,
        }}
      >
        Profile
      </Typography>

      <Box
        sx={{
          color: "#bdc9e5",
          textAlign: "center",
          mb: 1,
          fontFamily: profileFontFamily,
        }}
      >
        <Typography
          variant="body1"
          sx={{ color: "inherit", fontFamily: "inherit" }}
        >
          <Box component="strong" sx={{ color: "#38e07b" }}>
            Pages Recognised:
          </Box>{" "}
          {userData.pages_recognised_count || 0}
        </Typography>
      </Box>

      <AuthTextField
        label="Email"
        name="email"
        type="email"
        value={formData.email}
        onChange={(e) => handleChange("email", e.target.value)}
        sx={profileFieldSx}
      />

      {error && <ErrorAlert message={error} />}

      {successMessage && (
        <Box
          sx={{
            p: 2,
            backgroundColor: "rgba(56, 224, 123, 0.08)",
            border: "1px solid rgba(56, 224, 123, 0.35)",
            borderRadius: 1,
            color: "#38e07b",
            fontFamily: profileFontFamily,
          }}
        >
          {successMessage}
        </Box>
      )}

      <AuthTextField
        label="Name"
        name="name"
        value={formData.name}
        onChange={(e) => handleChange("name", e.target.value)}
        sx={profileFieldSx}
      />

      <AuthTextField
        label="Surname"
        name="surname"
        value={formData.surname}
        onChange={(e) => handleChange("surname", e.target.value)}
        sx={profileFieldSx}
      />

      <AuthTextField
        label="Telegram Username"
        name="telegram_username"
        value={formData.telegram_username}
        onChange={(e) => handleChange("telegram_username", e.target.value)}
        helperText="Use your Telegram @username so RuneRecall can link /start to your account."
        sx={profileFieldSx}
      />

      <LanguageAutocomplete
        label="Preferred Language (Mother Tongue)"
        value={formData.mother_tongue || ""}
        onChange={(value) => handleChange("mother_tongue", value)}
        sx={profileFieldSx}
      />

      <AuthTextField
        label="Timezone"
        name="timezone"
        value={formData.timezone}
        onChange={(e) => handleChange("timezone", e.target.value)}
        sx={profileFieldSx}
      />

      <AuthTextField
        label="New Password (optional)"
        name="password"
        type="password"
        value={formData.password}
        onChange={(e) => handleChange("password", e.target.value)}
        autoComplete="new-password"
        sx={profileFieldSx}
      />

      <AuthTextField
        label="Confirm New Password"
        name="confirmPassword"
        type="password"
        value={formData.confirmPassword}
        onChange={(e) => handleChange("confirmPassword", e.target.value)}
        autoComplete="new-password"
        sx={profileFieldSx}
      />

      <AuthButton
        type="submit"
        loading={loading}
        loadingText="Updating..."
        onClick={(e) => {
          e.preventDefault();
          handleSubmit(e);
        }}
        sx={{
          fontFamily: profileFontFamily,
          borderRadius: "0.75rem",
          boxShadow: "0 6px 24px rgba(56, 224, 123, 0.24)",
        }}
      >
        Update Profile
      </AuthButton>
    </Box>
  );
};

export default Profile;
