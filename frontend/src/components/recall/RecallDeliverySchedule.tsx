import { useEffect, useRef, useState } from "react";
import {
  Box,
  FormControl,
  InputLabel,
  MenuItem,
  Select,
  Stack,
  Typography,
} from "@mui/material";
import { Save } from "@mui/icons-material";
import type { RecallPendingAction, RecallState } from "../../types/recall";
import { CustomButton } from "../ui";

interface RecallDeliveryScheduleProps {
  recall: RecallState;
  disabled: boolean;
  pendingAction: RecallPendingAction | null;
  error: string | null;
  success: string | null;
  feedbackAction: RecallPendingAction["type"] | null;
  onSaveTimes: (startHour: number, endHour: number) => void;
  onToggleDelivery: (
    enabled: boolean,
    startHour: number,
    endHour: number
  ) => void;
}

const hours = Array.from({ length: 24 }, (_unused, hour) => hour);

const formatHour = (hour: number): string =>
  `${String(hour).padStart(2, "0")}:00`;

const normalizeHour = (hour: number, fallback: number): number =>
  Number.isInteger(hour) && hour >= 0 && hour <= 23 ? hour : fallback;

const selectSx = {
  color: "#f3f6ff",
  backgroundColor: "rgba(9, 15, 51, 0.55)",
  borderRadius: "0.75rem",
  "& .MuiOutlinedInput-notchedOutline": {
    borderColor: "rgba(99, 114, 173, 0.45)",
  },
  "&:hover .MuiOutlinedInput-notchedOutline": {
    borderColor: "rgba(99, 114, 173, 0.8)",
  },
  "&.Mui-focused .MuiOutlinedInput-notchedOutline": {
    borderColor: "#38e07b",
  },
  "& .MuiSvgIcon-root": { color: "#a8b6d8" },
  "&.Mui-disabled": {
    color: "#c2cee6",
    opacity: 1,
    backgroundColor: "rgba(25, 37, 72, 0.82)",
    "& .MuiOutlinedInput-notchedOutline": {
      borderColor: "rgba(126, 145, 194, 0.55)",
    },
    "& .MuiSvgIcon-root": { color: "#9eafd3" },
  },
};

const fieldSx = {
  "& .MuiInputLabel-root.Mui-disabled": {
    color: "#9eafd3",
    opacity: 1,
  },
};

const disabledButtonSx = {
  "&.Mui-disabled": {
    opacity: 1,
    color: "#b9c6e2",
    backgroundColor: "rgba(29, 42, 77, 0.82)",
    border: "1px solid rgba(126, 145, 194, 0.48)",
    boxShadow: "none",
  },
  "&.Mui-disabled .MuiSvgIcon-root": { color: "#9eafd3" },
};

const RecallDeliverySchedule = ({
  recall,
  disabled,
  pendingAction,
  error,
  success,
  feedbackAction,
  onSaveTimes,
  onToggleDelivery,
}: RecallDeliveryScheduleProps) => {
  const authoritativeStart = normalizeHour(recall.recall_start_hour, 9);
  const authoritativeEnd = normalizeHour(recall.recall_end_hour, 22);
  const [startHour, setStartHour] = useState(authoritativeStart);
  const [endHour, setEndHour] = useState(authoritativeEnd);
  const [equalAttempted, setEqualAttempted] = useState(false);
  const groupRef = useRef<HTMLDivElement>(null);
  const equalHours = startHour === endHour;
  const schedulePending =
    pendingAction?.type === "saveSettings" ||
    pendingAction?.type === "toggleDelivery";
  const isDisabled = disabled || !recall.configured || schedulePending;
  const isDirty =
    startHour !== authoritativeStart || endHour !== authoritativeEnd;

  // A successful response is authoritative. Failed requests leave the draft
  // untouched because the server values have not changed.
  useEffect(() => {
    setStartHour(authoritativeStart);
    setEndHour(authoritativeEnd);
    setEqualAttempted(false);
  }, [authoritativeStart, authoritativeEnd]);

  useEffect(() => {
    if (equalAttempted && equalHours) {
      groupRef.current?.focus();
    }
  }, [equalAttempted, equalHours]);

  const handleSave = () => {
    if (equalHours) {
      setEqualAttempted(true);
      return;
    }
    onSaveTimes(startHour, endHour);
  };

  const handleToggle = () => {
    if (equalHours) {
      setEqualAttempted(true);
      return;
    }
    onToggleDelivery(!recall.delivery_enabled, startHour, endHour);
  };

  const settingsError =
    feedbackAction === "saveSettings" || feedbackAction === "toggleDelivery"
      ? error
      : null;
  const settingsSuccess =
    feedbackAction === "saveSettings" || feedbackAction === "toggleDelivery"
      ? success
      : null;

  return (
    <Box
      component="section"
      aria-labelledby="recall-delivery-schedule-title"
      sx={{
        mt: { xs: 2.5, lg: 3 },
        p: { xs: 2.25, sm: 3 },
        border: "1px solid rgba(126,145,194,0.28)",
        borderRadius: "1rem",
        background:
          "radial-gradient(circle at 12% 5%, rgba(27, 42, 101, 0.38), rgba(6, 11, 40, 0.88))",
      }}
    >
      <Typography
        id="recall-delivery-schedule-title"
        component="h3"
        sx={{ color: "#f8fafc", fontSize: "1.3rem", fontWeight: 700 }}
      >
        Delivery schedule
      </Typography>
      <Typography sx={{ color: "#aebbd8", lineHeight: 1.65, mt: 0.75 }}>
        Delivery runs on the global cadence. The start hour is inclusive and
        the end hour is exclusive; windows can run overnight.
      </Typography>

      <Box
        ref={groupRef}
        role="group"
        tabIndex={-1}
        aria-labelledby="recall-delivery-schedule-title"
        aria-describedby={equalHours ? "recall-schedule-error" : undefined}
        sx={{ outline: "none", mt: 2.5 }}
      >
        <Stack direction={{ xs: "column", sm: "row" }} spacing={2}>
          <FormControl fullWidth disabled={isDisabled} sx={fieldSx}>
            <InputLabel id="recall-start-hour-label">Starts</InputLabel>
            <Select
              labelId="recall-start-hour-label"
              id="recall-start-hour"
              value={startHour}
              label="Starts"
              onChange={(event) => {
                setStartHour(Number(event.target.value));
                setEqualAttempted(Number(event.target.value) === endHour);
              }}
              sx={selectSx}
            >
              {hours.map((hour) => (
                <MenuItem key={hour} value={hour}>
                  {formatHour(hour)}
                </MenuItem>
              ))}
            </Select>
          </FormControl>
          <FormControl fullWidth disabled={isDisabled} sx={fieldSx}>
            <InputLabel id="recall-end-hour-label">Ends</InputLabel>
            <Select
              labelId="recall-end-hour-label"
              id="recall-end-hour"
              value={endHour}
              label="Ends"
              onChange={(event) => {
                setEndHour(Number(event.target.value));
                setEqualAttempted(Number(event.target.value) === startHour);
              }}
              sx={selectSx}
            >
              {hours.map((hour) => (
                <MenuItem key={hour} value={hour}>
                  {formatHour(hour)}
                </MenuItem>
              ))}
            </Select>
          </FormControl>
        </Stack>
        {equalHours && (
          <Typography
            id="recall-schedule-error"
            role="alert"
            sx={{ color: "#ff9a9f", mt: 1, fontSize: "0.9rem" }}
          >
            Start and end times must be different.
          </Typography>
        )}
      </Box>

      <Typography sx={{ color: "#bdc9e4", mt: 2, fontSize: "0.94rem" }}>
        Effective timezone: <strong>{recall.timezone || "UTC"}</strong>. Change it in
        Profile.
      </Typography>

      <Stack
        direction={{ xs: "column", sm: "row" }}
        spacing={1.5}
        sx={{ mt: 2.5 }}
      >
        <CustomButton
          type="button"
          variant="save"
          startIcon={<Save fontSize="small" />}
          disabled={isDisabled || !isDirty || equalHours}
          onClick={handleSave}
          aria-label="Save times"
          sx={disabledButtonSx}
        >
          Save times
        </CustomButton>
        <CustomButton
          type="button"
          variant="secondary"
          disabled={isDisabled || equalHours}
          onClick={handleToggle}
          aria-label={
            recall.delivery_enabled ? "Stop delivery" : "Start delivery"
          }
          sx={{
            border: "1px solid rgba(156,173,216,0.34)",
            ...disabledButtonSx,
          }}
        >
          {recall.delivery_enabled ? "Stop delivery" : "Start delivery"}
        </CustomButton>
      </Stack>

      {settingsSuccess && (
        <Box role="status" aria-live="polite" sx={{ color: "#65eaa0", mt: 2 }}>
          {settingsSuccess}
        </Box>
      )}
      {settingsError && (
        <Box role="alert" aria-live="assertive" sx={{ color: "#ff9a9f", mt: 2 }}>
          {settingsError}
        </Box>
      )}
    </Box>
  );
};

export default RecallDeliverySchedule;
