import { Box } from "@mui/material";

interface StudentAvatarProps {
  label: string;
}

export const StudentAvatar: React.FC<StudentAvatarProps> = ({ label }) => (
  <Box
    aria-label={`${label}, student`}
    role="img"
    sx={(theme) => ({
      width: 32,
      height: 32,
      borderRadius: "50%",
      display: "inline-flex",
      alignItems: "center",
      justifyContent: "center",
      flexShrink: 0,
      alignSelf: "flex-end",
      background: `radial-gradient(circle at 30% 25%, ${theme.palette.primary.light}, ${theme.palette.primary.main})`,
      border: `1px solid ${theme.palette.primary.light}`,
      boxShadow: `0 10px 20px ${theme.palette.primary.dark}`,
      color: theme.palette.primary.contrastText,
      fontSize: "0.75rem",
      fontWeight: 800,
      letterSpacing: "0.04em",
      textTransform: "uppercase",
    })}
  >
    {label}
  </Box>
);
