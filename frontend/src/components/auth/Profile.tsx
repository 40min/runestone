import React, { useState, useEffect } from "react";
import type { FormEvent } from "react";
import { Box, TextField } from "@mui/material";
import { useAuth } from "../../context/AuthContext";
import { useAuthActions } from "../../hooks/useAuth";

const Profile: React.FC = () => {
  const { userData } = useAuth();
  const { updateProfile, loading, error } = useAuthActions();
  const [formData, setFormData] = useState({
    name: "",
    surname: "",
    timezone: "UTC",
    password: "",
    confirmPassword: "",
  });
  const [successMessage, setSuccessMessage] = useState("");
  const [localError, setLocalError] = useState("");

  useEffect(() => {
    if (userData) {
      setFormData({
        name: userData.name || "",
        surname: userData.surname || "",
        timezone: userData.timezone || "UTC",
        password: "",
        confirmPassword: "",
      });
    }
  }, [userData]);

  const handleChange = (field: string, value: string) => {
    setFormData((prev) => ({ ...prev, [field]: value }));
  };

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setLocalError("");
    setSuccessMessage("");

    if (formData.password && formData.password !== formData.confirmPassword) {
      setLocalError("Passwords do not match");
      return;
    }

    if (formData.password && formData.password.length < 6) {
      setLocalError("Password must be at least 6 characters");
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

      await updateProfile(updateData);
      setSuccessMessage("Profile updated successfully!");
      setFormData((prev) => ({
        ...prev,
        password: "",
        confirmPassword: "",
      }));
    } catch {
      // Error is handled by the hook
    }
  };

  if (!userData) {
    return null;
  }

  const displayError = error || localError;

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
        <div>Email: {userData.email}</div>
        <div>Stats: {userData.pages_recognised_count} page(s) recognized</div>
      </Box>

      {displayError && (
        <Box
          sx={{
            p: 2,
            backgroundColor: "rgba(211, 47, 47, 0.1)",
            border: "1px solid rgba(211, 47, 47, 0.5)",
            borderRadius: 1,
            color: "#f44336",
          }}
        >
          {displayError}
        </Box>
      )}

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
      {/* TODO: rewrite with standaetised components */}
      <TextField
        label="Name"
        value={formData.name}
        onChange={(e) => handleChange("name", e.target.value)}
        fullWidth
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

      <TextField
        label="Surname"
        value={formData.surname}
        onChange={(e) => handleChange("surname", e.target.value)}
        fullWidth
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

      <TextField
        label="Timezone"
        value={formData.timezone}
        onChange={(e) => handleChange("timezone", e.target.value)}
        fullWidth
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

      <TextField
        label="New Password (optional)"
        type="password"
        value={formData.password}
        onChange={(e) => handleChange("password", e.target.value)}
        fullWidth
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

      <TextField
        label="Confirm New Password"
        type="password"
        value={formData.confirmPassword}
        onChange={(e) => handleChange("confirmPassword", e.target.value)}
        fullWidth
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
          padding: "10px 20px",
          backgroundColor: "var(--primary-color)",
          color: "white",
          border: "none",
          borderRadius: "6px",
          cursor: loading ? "not-allowed" : "pointer",
          fontSize: "14px",
          fontWeight: "bold",
          opacity: loading ? 0.6 : 1,
          "&:hover": {
            opacity: 0.9,
          },
        }}
      >
        {loading ? "Updating..." : "Update Profile"}
      </Box>
    </Box>
  );
};

export default Profile;
