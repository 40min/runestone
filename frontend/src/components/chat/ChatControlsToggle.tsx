import { ExpandLess, ExpandMore } from "@mui/icons-material";
import { ButtonBase } from "@mui/material";

interface ChatControlsToggleProps {
  expanded: boolean;
  disabled: boolean;
  onToggle: () => void;
}

export const ChatControlsToggle: React.FC<ChatControlsToggleProps> = ({
  expanded,
  disabled,
  onToggle,
}) => (
  <ButtonBase
    onClick={onToggle}
    disabled={disabled}
    aria-expanded={expanded}
    aria-controls="teacher-chat-controls-panel"
    aria-label={expanded ? "Hide chat controls" : "Show chat controls"}
    sx={{
      position: "absolute",
      top: 0,
      left: "50%",
      transform: "translate(-50%, -50%)",
      zIndex: 1,
      display: "inline-flex",
      alignItems: "center",
      justifyContent: "center",
      width: 64,
      height: 34,
      borderRadius: "10px",
      border: "1px solid rgba(91, 143, 238, 0.72)",
      background: expanded
        ? "linear-gradient(180deg, rgba(42, 92, 184, 0.96), rgba(19, 49, 111, 0.98))"
        : "linear-gradient(180deg, rgba(19, 43, 94, 0.98), rgba(9, 24, 63, 0.98))",
      boxShadow: expanded
        ? "0 0 0 1px rgba(111, 164, 255, 0.18), 0 0 18px rgba(55, 118, 230, 0.44)"
        : "0 0 14px rgba(55, 118, 230, 0.28)",
      color: "#eef5ff",
      transition:
        "transform 180ms ease, box-shadow 180ms ease, background 180ms ease, border-color 180ms ease",
      "&:hover": {
        transform: "translate(-50%, -50%) scale(1.03)",
        borderColor: "rgba(127, 174, 255, 0.9)",
        boxShadow:
          "0 0 0 1px rgba(127, 174, 255, 0.2), 0 0 20px rgba(55, 118, 230, 0.48)",
      },
      "&:focus-visible": {
        outline: "none",
        transform: "translate(-50%, -50%) scale(1.03)",
        boxShadow:
          "0 0 0 2px #060b26, 0 0 0 4px rgba(127, 174, 255, 0.9), 0 0 22px rgba(55, 118, 230, 0.5)",
      },
      "&.Mui-disabled": {
        opacity: 0.58,
        color: "#b9c8e8",
        cursor: "not-allowed",
      },
    }}
  >
    {expanded ? (
      <ExpandLess fontSize="small" />
    ) : (
      <ExpandMore fontSize="small" />
    )}
  </ButtonBase>
);
