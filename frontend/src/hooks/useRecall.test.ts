import { act, renderHook, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { useRecall } from "./useRecall";
import type { RecallState } from "../types/recall";

const { mockGet, mockPost, mockPatch } = vi.hoisted(() => ({
  mockGet: vi.fn(),
  mockPost: vi.fn(),
  mockPatch: vi.fn(),
}));

vi.mock("../utils/api", () => ({
  useApi: () => ({
    get: mockGet,
    post: mockPost,
    patch: mockPatch,
  }),
}));

const initialRecall: RecallState = {
  configured: true,
  delivery_enabled: true,
  recall_start_hour: 9,
  recall_end_hour: 22,
  timezone: "Europe/Helsinki",
  words: [
    {
      id: 1,
      word_phrase: "hej",
      translation: "hello",
      example_phrase: null,
    },
  ],
};

const createDeferred = <T,>() => {
  let resolve!: (value: T | PromiseLike<T>) => void;
  let reject!: (reason?: unknown) => void;
  const promise = new Promise<T>((promiseResolve, promiseReject) => {
    resolve = promiseResolve;
    reject = promiseReject;
  });
  return { promise, resolve, reject };
};

describe("useRecall", () => {
  beforeEach(() => {
    mockGet.mockReset();
    mockPost.mockReset();
    mockPatch.mockReset();
    mockGet.mockResolvedValue(initialRecall);
  });

  it("loads the current recall state on mount", async () => {
    const { result } = renderHook(() => useRecall());

    expect(result.current.loading).toBe(true);

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    expect(mockGet).toHaveBeenCalledOnce();
    expect(mockGet).toHaveBeenCalledWith("/api/recall");
    expect(result.current.recall).toEqual(initialRecall);
    expect(result.current.error).toBeNull();
  });

  it("reports an initial load error and can retry", async () => {
    mockGet
      .mockRejectedValueOnce(new Error("Network unavailable"))
      .mockResolvedValueOnce(initialRecall);
    const { result } = renderHook(() => useRecall());

    await waitFor(() => {
      expect(result.current.error).toBe("Network unavailable");
    });
    expect(result.current.recall).toBeNull();

    await act(async () => {
      await result.current.refetch();
    });

    expect(result.current.recall).toEqual(initialRecall);
    expect(result.current.error).toBeNull();
  });

  it("replaces the full queue with the authoritative postpone response", async () => {
    const authoritativeResponse: RecallState = {
      ...initialRecall,
      words: [
        {
          id: 8,
          word_phrase: "ersättare",
          translation: "replacement",
          example_phrase: null,
        },
      ],
    };
    mockPost.mockResolvedValueOnce(authoritativeResponse);
    const { result } = renderHook(() => useRecall());
    await waitFor(() => expect(result.current.loading).toBe(false));

    await act(async () => {
      await result.current.postponeWord(1, "hej");
    });

    expect(mockPost).toHaveBeenCalledWith(
      "/api/recall/words/1/postpone"
    );
    expect(result.current.recall).toEqual(authoritativeResponse);
    expect(result.current.success).toBe("Postponed hej.");
    expect(result.current.pendingAction).toBeNull();
  });

  it("sends the selected vocabulary id when removing from learning", async () => {
    const authoritativeResponse: RecallState = {
      ...initialRecall,
      words: [],
    };
    mockPost.mockResolvedValueOnce(authoritativeResponse);
    const { result } = renderHook(() => useRecall());
    await waitFor(() => expect(result.current.loading).toBe(false));

    await act(async () => {
      await result.current.removeWord(1, "hej");
    });

    expect(mockPost).toHaveBeenCalledWith("/api/recall/words/1/remove");
    expect(result.current.recall).toEqual(authoritativeResponse);
    expect(result.current.success).toBe("Removed hej from learning.");
  });

  it("saves both schedule hours and replaces the authoritative response", async () => {
    const authoritativeResponse: RecallState = {
      ...initialRecall,
      recall_start_hour: 8,
      recall_end_hour: 18,
    };
    mockPatch.mockResolvedValueOnce(authoritativeResponse);
    const { result } = renderHook(() => useRecall());
    await waitFor(() => expect(result.current.loading).toBe(false));

    await act(async () => {
      await result.current.saveSchedule(8, 18);
    });

    expect(mockPatch).toHaveBeenCalledWith("/api/recall/settings", {
      recall_start_hour: 8,
      recall_end_hour: 18,
    });
    expect(result.current.recall).toEqual(authoritativeResponse);
  });

  it("sends draft hours with the requested delivery state", async () => {
    mockPatch.mockResolvedValueOnce({ ...initialRecall, delivery_enabled: false });
    const { result } = renderHook(() => useRecall());
    await waitFor(() => expect(result.current.loading).toBe(false));

    await act(async () => {
      await result.current.setDeliveryEnabled(false, 8, 18);
    });

    expect(mockPatch).toHaveBeenCalledWith("/api/recall/settings", {
      recall_start_hour: 8,
      recall_end_hour: 18,
      delivery_enabled: false,
    });
    expect(result.current.success).toBe("Recall delivery stopped.");
  });

  it("retains authoritative recall state when settings mutation fails", async () => {
    mockPatch.mockRejectedValueOnce(new Error("settings unavailable"));
    const { result } = renderHook(() => useRecall());
    await waitFor(() => expect(result.current.loading).toBe(false));

    await act(async () => {
      await result.current.saveSchedule(8, 18);
    });

    expect(result.current.recall).toEqual(initialRecall);
    expect(result.current.error).toBe("settings unavailable");
    expect(result.current.feedbackAction).toBe("saveSettings");
  });

  it("retains the current queue when a mutation fails", async () => {
    mockPost.mockRejectedValueOnce(new Error("Word is no longer selected"));
    const { result } = renderHook(() => useRecall());
    await waitFor(() => expect(result.current.loading).toBe(false));

    await act(async () => {
      await result.current.postponeWord(1, "hej");
    });

    expect(result.current.recall).toEqual(initialRecall);
    expect(result.current.error).toBe("Word is no longer selected");
    expect(result.current.success).toBeNull();
    expect(result.current.pendingAction).toBeNull();
  });

  it("prevents duplicate mutation submissions", async () => {
    const deferred = createDeferred<RecallState>();
    mockPost.mockReturnValueOnce(deferred.promise);
    const { result } = renderHook(() => useRecall());
    await waitFor(() => expect(result.current.loading).toBe(false));

    let firstRequest!: Promise<void>;
    act(() => {
      firstRequest = result.current.refreshSelection();
      void result.current.refreshSelection();
    });

    expect(mockPost).toHaveBeenCalledOnce();
    expect(mockPost).toHaveBeenCalledWith("/api/recall/bump");
    expect(result.current.pendingAction).toEqual({ type: "refresh" });

    deferred.resolve({
      ...initialRecall,
      words: [{ id: 9, word_phrase: "ny" }],
    });
    await act(async () => {
      await firstRequest;
    });

    expect(result.current.recall?.words).toEqual([
      { id: 9, word_phrase: "ny" },
    ]);
    expect(result.current.pendingAction).toBeNull();
  });

  it("clears feedback explicitly", async () => {
    mockPost.mockRejectedValueOnce(new Error("Mutation failed"));
    const { result } = renderHook(() => useRecall());
    await waitFor(() => expect(result.current.loading).toBe(false));
    await act(async () => {
      await result.current.refreshSelection();
    });

    act(() => {
      result.current.clearFeedback();
    });

    expect(result.current.error).toBeNull();
    expect(result.current.success).toBeNull();
  });
});
