import { useCallback, useEffect, useRef, useState } from "react";
import type {
  RecallPendingAction,
  RecallState,
} from "../types/recall";
import { useApi } from "../utils/api";

interface UseRecallReturn {
  recall: RecallState | null;
  loading: boolean;
  pendingAction: RecallPendingAction | null;
  error: string | null;
  success: string | null;
  refetch: () => Promise<void>;
  refreshSelection: () => Promise<void>;
  postponeWord: (vocabularyId: number, wordPhrase: string) => Promise<void>;
  removeWord: (vocabularyId: number, wordPhrase: string) => Promise<void>;
  saveSchedule: (startHour: number, endHour: number) => Promise<void>;
  setDeliveryEnabled: (
    enabled: boolean,
    startHour: number,
    endHour: number
  ) => Promise<void>;
  clearFeedback: () => void;
  feedbackAction: RecallPendingAction["type"] | null;
}

export const useRecall = (): UseRecallReturn => {
  const [recall, setRecall] = useState<RecallState | null>(null);
  const [loading, setLoading] = useState(true);
  const [pendingAction, setPendingAction] =
    useState<RecallPendingAction | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [feedbackAction, setFeedbackAction] = useState<
    RecallPendingAction["type"] | null
  >(null);
  const mutationInFlightRef = useRef(false);
  const hasFetchedRef = useRef(false);
  const { get, post, patch } = useApi();

  const refetch = useCallback(async () => {
    setLoading(true);
    setError(null);
    setSuccess(null);
    setFeedbackAction(null);
    try {
      setRecall(await get<RecallState>("/api/recall"));
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "Failed to load recall selection"
      );
    } finally {
      setLoading(false);
    }
  }, [get]);

  useEffect(() => {
    if (hasFetchedRef.current) {
      return;
    }
    hasFetchedRef.current = true;
    void refetch();
  }, [refetch]);

  const runMutation = useCallback(
    async (
      endpoint: string,
      action: RecallPendingAction,
      successMessage: string
    ) => {
      if (mutationInFlightRef.current) {
        return;
      }

      mutationInFlightRef.current = true;
      setPendingAction(action);
      setError(null);
      setSuccess(null);
      setFeedbackAction(null);
      try {
        const updated = await post<RecallState>(endpoint);
        setRecall(updated);
        setSuccess(successMessage);
        setFeedbackAction(action.type);
      } catch (requestError) {
        setError(
          requestError instanceof Error
            ? requestError.message
            : "Failed to update recall selection"
        );
        setFeedbackAction(action.type);
      } finally {
        mutationInFlightRef.current = false;
        setPendingAction(null);
      }
    },
    [post]
  );

  const runSettingsMutation = useCallback(
    async (
      body: {
        recall_start_hour: number;
        recall_end_hour: number;
        delivery_enabled?: boolean;
      },
      action: RecallPendingAction,
      successMessage: string
    ) => {
      if (mutationInFlightRef.current) {
        return;
      }

      mutationInFlightRef.current = true;
      setPendingAction(action);
      setError(null);
      setSuccess(null);
      setFeedbackAction(null);
      try {
        const updated = await patch<RecallState>("/api/recall/settings", body);
        setRecall(updated);
        setSuccess(successMessage);
        setFeedbackAction(action.type);
      } catch (requestError) {
        setError(
          requestError instanceof Error
            ? requestError.message
            : "Failed to update recall settings"
        );
        setFeedbackAction(action.type);
      } finally {
        mutationInFlightRef.current = false;
        setPendingAction(null);
      }
    },
    [patch]
  );

  const refreshSelection = useCallback(
    () =>
      runMutation(
        "/api/recall/bump",
        { type: "refresh" },
        "Recall selection refreshed."
      ),
    [runMutation]
  );

  const postponeWord = useCallback(
    (vocabularyId: number, wordPhrase: string) =>
      runMutation(
        `/api/recall/words/${vocabularyId}/postpone`,
        { type: "postpone", vocabularyId },
        `Postponed ${wordPhrase}.`
      ),
    [runMutation]
  );

  const removeWord = useCallback(
    (vocabularyId: number, wordPhrase: string) =>
      runMutation(
        `/api/recall/words/${vocabularyId}/remove`,
        { type: "remove", vocabularyId },
        `Removed ${wordPhrase} from learning.`
      ),
    [runMutation]
  );

  const saveSchedule = useCallback(
    (startHour: number, endHour: number) =>
      runSettingsMutation(
        { recall_start_hour: startHour, recall_end_hour: endHour },
        { type: "saveSettings" },
        "Recall delivery times saved."
      ),
    [runSettingsMutation]
  );

  const setDeliveryEnabled = useCallback(
    (enabled: boolean, startHour: number, endHour: number) =>
      runSettingsMutation(
        {
          recall_start_hour: startHour,
          recall_end_hour: endHour,
          delivery_enabled: enabled,
        },
        { type: "toggleDelivery", enabled },
        `Recall delivery ${enabled ? "started" : "stopped"}.`
      ),
    [runSettingsMutation]
  );

  const clearFeedback = useCallback(() => {
    setError(null);
    setSuccess(null);
    setFeedbackAction(null);
  }, []);

  return {
    recall,
    loading,
    pendingAction,
    error,
    success,
    refetch,
    refreshSelection,
    postponeWord,
    removeWord,
    saveSchedule,
    setDeliveryEnabled,
    clearFeedback,
    feedbackAction,
  };
};
