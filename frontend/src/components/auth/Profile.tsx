import React, { useState, useEffect } from "react";
import type { FormEvent } from "react";
import { Box, Typography } from "@mui/material";
import { useAuth } from "../../context/AuthContext";
import { useAuthActions } from "../../hooks/useAuth";
import { ErrorAlert } from "../ui";
import AuthButton from "./AuthButton";
import AuthTextField from "./AuthTextField";

const Profile: React.FC = () => {
  const { userData } = useAuth();
  const { updateProfile, loading } = useAuthActions();
  const [formData, setFormData] = useState({
    name: "",
    surname: "",
    timezone: "UTC",
    password: "",
    confirmPassword: "",
    email: "",
  });
  const [successMessage, setSuccessMessage] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    if (userData) {
      setFormData({
        name: userData.name || "",
        surname: userData.surname || "",
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
        gap: 2,
        maxWidth: 600,
        mx: "auto",
        p: 4,
        backgroundColor: "rgba(255, 255, 255, 0.05)",
        borderRadius: 2,
        backdropFilter: "blur(10px)",
      }}
    >
      <h2 className="text-3xl font-bold text-white text-center mb-2">
        Profile
      </h2>

      <Box
        sx={{ color: "rgba(255, 255, 255, 0.7)", textAlign: "center", mb: 2 }}
      >
        <Typography variant="body1" sx={{ mb: 1 }}>
          <strong>Pages Recognised:</strong>{" "}
          {userData.pages_recognised_count || 0}
        </Typography>
        <Typography variant="body1" sx={{ mb: 1 }}>
          <strong>Words Learning:</strong> {userData.words_in_learn_count || 0}
        </Typography>
        <Typography variant="body1" sx={{ mb: 1 }}>
          <strong>Words Learned:</strong> {userData.words_learned_count || 0}
        </Typography>
      </Box>

      <AuthTextField
        label="Email"
        name="email"
        type="email"
        value={formData.email}
        onChange={(e) => handleChange("email", e.target.value)}
      />

      {error && <ErrorAlert message={error} />}

      {successMessage && (
        <Box
          sx={{
            p: 2,
            backgroundColor: "rgba(56, 142, 60, 0.1)",
            border: "1px solid rgba(56, 142, 60, 0.5)",
            borderRadius: 1,
            color: "#4caf50",
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
      />

      <AuthTextField
        label="Surname"
        name="surname"
        value={formData.surname}
        onChange={(e) => handleChange("surname", e.target.value)}
      />

      <AuthTextField
        label="Timezone"
        name="timezone"
        value={formData.timezone}
        onChange={(e) => handleChange("timezone", e.target.value)}
      />

      <AuthTextField
        label="New Password (optional)"
        name="password"
        type="password"
        value={formData.password}
        onChange={(e) => handleChange("password", e.target.value)}
        autoComplete="new-password"
      />

      <AuthTextField
        label="Confirm New Password"
        name="confirmPassword"
        type="password"
        value={formData.confirmPassword}
        onChange={(e) => handleChange("confirmPassword", e.target.value)}
        autoComplete="new-password"
      />

      <AuthButton
        type="submit"
        loading={loading}
        loadingText="Updating..."
        onClick={(e) => {
          e.preventDefault();
          handleSubmit(e);
        }}
      >
        Update Profile
      </AuthButton>
    </Box>
  );
};

export default Profile;
