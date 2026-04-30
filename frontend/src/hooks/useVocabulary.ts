import { useState, useEffect, useRef, useCallback } from "react";
import { useApi } from "../utils/api";
import type { VocabularyImprovementMode } from "../constants";

interface SavedVocabularyItem {
  id: number;
  user_id: number;
  word_phrase: string;
  translation: string;
  example_phrase: string | null;
  extra_info: string | null;
  in_learn: boolean;
  priority_learn: number;
  last_learned: string | null;
  learned_times: number;
  created_at: string;
  updated_at: string;
  updated?: string | null;
}

export interface VocabularyStats {
  words_in_learn_count: number;
  words_skipped_count: number;
  overall_words_count: number;
  words_prioritized_count: number;
}

interface UseVocabularyReturn {
  vocabulary: SavedVocabularyItem[];
  loading: boolean;
  error: string | null;
  refetch: () => Promise<void>;
}

interface UseRecentVocabularyReturn {
  recentVocabulary: SavedVocabularyItem[];
  loading: boolean;
  loadingMore: boolean;
  error: string | null;
  refetch: () => Promise<void>;
  loadMore: () => Promise<void>;
  hasMore: boolean;
  isEditModalOpen: boolean;
  editingItem: SavedVocabularyItem | null;
  openEditModal: (item: SavedVocabularyItem | null) => void;
  closeEditModal: () => void;
  updateVocabularyItem: (
    id: number,
    updates: Partial<SavedVocabularyItem>
  ) => Promise<void>;
  createVocabularyItem: (item: Partial<SavedVocabularyItem>) => Promise<void>;
  deleteVocabularyItem: (id: number) => Promise<void>;
}

interface UseVocabularyStatsReturn {
  stats: VocabularyStats | null;
  loading: boolean;
  error: string | null;
  refetch: () => Promise<void>;
}

const useVocabulary = (): UseVocabularyReturn => {
  const [vocabulary, setVocabulary] = useState<SavedVocabularyItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const hasFetchedRef = useRef(false);
  const { get } = useApi();

  const fetchVocabulary = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data: SavedVocabularyItem[] = await get<SavedVocabularyItem[]>(
        "/api/vocabulary"
      );
      setVocabulary(data);
    } catch (err) {
      const errorMessage =
        err instanceof Error ? err.message : "Failed to fetch vocabulary";
      setError(errorMessage);
    } finally {
      setLoading(false);
    }
  }, [get]);

  useEffect(() => {
    if (!hasFetchedRef.current) {
      hasFetchedRef.current = true;
      fetchVocabulary();
    }
  }, [fetchVocabulary]);

  return {
    vocabulary,
    loading,
    error,
    refetch: fetchVocabulary,
  };
};

export default useVocabulary;

export const useVocabularyStats = (): UseVocabularyStatsReturn => {
  const [stats, setStats] = useState<VocabularyStats | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const hasFetchedRef = useRef(false);
  const { get } = useApi();

  const fetchStats = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await get<VocabularyStats>("/api/vocabulary/stats");
      setStats(data);
    } catch (err) {
      const errorMessage =
        err instanceof Error ? err.message : "Failed to fetch vocabulary stats";
      setError(errorMessage);
    } finally {
      setLoading(false);
    }
  }, [get]);

  useEffect(() => {
    if (!hasFetchedRef.current) {
      hasFetchedRef.current = true;
      fetchStats();
    }
  }, [fetchStats]);

  return {
    stats,
    loading,
    error,
    refetch: fetchStats,
  };
};

export const useRecentVocabulary = (
  searchQuery?: string,
  preciseSearch = false
): UseRecentVocabularyReturn => {
  const [recentVocabulary, setRecentVocabulary] = useState<
    SavedVocabularyItem[]
  >([]);
  const [loading, setLoading] = useState(false);
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [hasMore, setHasMore] = useState(true);
  const [isEditModalOpen, setIsEditModalOpen] = useState(false);
  const [editingItem, setEditingItem] = useState<SavedVocabularyItem | null>(
    null
  );
  const offsetRef = useRef(0);
  const loadMoreInFlightRef = useRef(false);
  const requestIdRef = useRef(0);
  const { get, post, put, delete: apiDelete } = useApi();

  const getPageSize = useCallback(() => (searchQuery ? 100 : 20), [searchQuery]);

  const fetchRecentVocabularyPage = useCallback(async (reset = true) => {
    if (!reset && loadMoreInFlightRef.current) {
      return;
    }
    const requestId = reset ? requestIdRef.current + 1 : requestIdRef.current;
    if (reset) {
      requestIdRef.current = requestId;
    } else {
      loadMoreInFlightRef.current = true;
    }
    const pageSize = getPageSize();
    const offset = reset ? 0 : offsetRef.current;

    if (reset) {
      setLoading(true);
    } else {
      setLoadingMore(true);
    }
    setError(null);
    try {
      const params = new URLSearchParams();
      if (searchQuery) {
        params.append("search_query", searchQuery);
        params.append("precise", preciseSearch ? "true" : "false");
      }
      params.append("limit", pageSize.toString());
      params.append("offset", offset.toString());
      const data: SavedVocabularyItem[] = await get<SavedVocabularyItem[]>(
        `/api/vocabulary?${params.toString()}`
      );
      if (requestId !== requestIdRef.current) {
        return;
      }
      if (reset) {
        setRecentVocabulary(data);
      } else {
        setRecentVocabulary((prev) => {
          const seen = new Set(prev.map((item) => item.id));
          return [...prev, ...data.filter((item) => !seen.has(item.id))];
        });
      }
      offsetRef.current = offset + data.length;
      setHasMore(data.length === pageSize);
    } catch (err) {
      if (requestId !== requestIdRef.current) {
        return;
      }
      const errorMessage =
        err instanceof Error
          ? err.message
          : "Failed to fetch recent vocabulary";
      setError(errorMessage);
    } finally {
      if (requestId === requestIdRef.current) {
        setLoading(false);
        setLoadingMore(false);
      }
      if (!reset) {
        loadMoreInFlightRef.current = false;
      }
    }
  }, [getPageSize, searchQuery, preciseSearch, get]);

  const fetchRecentVocabulary = useCallback(async () => {
    offsetRef.current = 0;
    setHasMore(true);
    await fetchRecentVocabularyPage(true);
  }, [fetchRecentVocabularyPage]);

  const loadMore = useCallback(async () => {
    if (!hasMore || loading || loadingMore) {
      return;
    }
    await fetchRecentVocabularyPage(false);
  }, [fetchRecentVocabularyPage, hasMore, loading, loadingMore]);

  const openEditModal = useCallback((item: SavedVocabularyItem | null) => {
    setEditingItem(item);
    setIsEditModalOpen(true);
  }, []);

  const closeEditModal = useCallback(() => {
    setIsEditModalOpen(false);
    setEditingItem(null);
  }, []);

  const updateVocabularyItem = useCallback(
    async (id: number, updates: Partial<SavedVocabularyItem>) => {
      await put<SavedVocabularyItem>(`/api/vocabulary/${id}`, updates);
      await fetchRecentVocabulary();
      closeEditModal();
    },
    [closeEditModal, fetchRecentVocabulary, put]
  );

  const createVocabularyItem = useCallback(
    async (item: Partial<SavedVocabularyItem>) => {
      const newItem: SavedVocabularyItem = await post<SavedVocabularyItem>(
        "/api/vocabulary/item",
        item
      );
      setRecentVocabulary((prev) => [newItem, ...prev]);
      closeEditModal();
    },
    [closeEditModal, post]
  );

  const deleteVocabularyItem = useCallback(
    async (id: number) => {
      await apiDelete(`/api/vocabulary/${id}`);
      setRecentVocabulary((prev) => {
        const next = prev.filter((item) => item.id !== id);
        if (next.length !== prev.length) {
          offsetRef.current = Math.max(0, offsetRef.current - 1);
        }
        return next;
      });
      closeEditModal();
    },
    [closeEditModal, apiDelete]
  );

  useEffect(() => {
    fetchRecentVocabulary();
  }, [searchQuery, preciseSearch, fetchRecentVocabulary]);

  return {
    recentVocabulary,
    loading,
    loadingMore,
    error,
    refetch: fetchRecentVocabulary,
    loadMore,
    hasMore,
    isEditModalOpen,
    editingItem,
    openEditModal,
    closeEditModal,
    updateVocabularyItem,
    createVocabularyItem,
    deleteVocabularyItem,
  };
};

export const improveVocabularyItem = async (
  api: ReturnType<typeof useApi>,
  wordPhrase: string,
  mode: VocabularyImprovementMode
): Promise<{
  translation?: string;
  example_phrase?: string;
  extra_info?: string;
}> => {
  return api.post<{
    translation?: string;
    example_phrase?: string;
    extra_info?: string;
  }>("/api/vocabulary/improve", {
    word_phrase: wordPhrase,
    mode: mode,
  });
};
