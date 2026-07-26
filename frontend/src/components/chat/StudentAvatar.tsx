import { Box } from "@mui/material";

interface StudentAvatarProps {
  label: string;
}

export const StudentAvatar: React.FC<StudentAvatarProps> = ({ label }) => (
  <Box
    aria-label={`${label}, student`}
    role="img"
    sx={{
      width: 32,
      height: 32,
      borderRadius: "50%",
      display: "inline-flex",
      alignItems: "center",
      justifyContent: "center",
      flexShrink: 0,
      alignSelf: "flex-end",
      background:
        "radial-gradient(circle at 30% 25%, #80b8ff, #316bd7 68%, #214b9e)",
      border: "1px solid rgba(145, 194, 255, 0.92)",
      boxShadow:
        "0 0 0 1px rgba(92, 157, 255, 0.24), 0 0 18px rgba(55, 126, 235, 0.56)",
      color: "#f7fbff",
      fontSize: "0.75rem",
      fontWeight: 800,
      letterSpacing: "0.04em",
      textTransform: "uppercase",
    }}
  >
    {label}
  </Box>
);
