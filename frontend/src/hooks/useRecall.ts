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
  clearFeedback: () => void;
}

export const useRecall = (): UseRecallReturn => {
  const [recall, setRecall] = useState<RecallState | null>(null);
  const [loading, setLoading] = useState(true);
  const [pendingAction, setPendingAction] =
    useState<RecallPendingAction | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const mutationInFlightRef = useRef(false);
  const hasFetchedRef = useRef(false);
  const { get, post } = useApi();

  const refetch = useCallback(async () => {
    setLoading(true);
    setError(null);
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
      try {
        const updated = await post<RecallState>(endpoint);
        setRecall(updated);
        setSuccess(successMessage);
      } catch (requestError) {
        setError(
          requestError instanceof Error
            ? requestError.message
            : "Failed to update recall selection"
        );
      } finally {
        mutationInFlightRef.current = false;
        setPendingAction(null);
      }
    },
    [post]
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

  const clearFeedback = useCallback(() => {
    setError(null);
    setSuccess(null);
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
    clearFeedback,
  };
};
