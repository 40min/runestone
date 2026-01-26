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
  priority_learn: boolean;
  last_learned: string | null;
  learned_times: number;
  created_at: string;
  updated_at: string;
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
  error: string | null;
  refetch: () => Promise<void>;
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

export const useRecentVocabulary = (
  searchQuery?: string,
  preciseSearch = false
): UseRecentVocabularyReturn => {
  const [recentVocabulary, setRecentVocabulary] = useState<
    SavedVocabularyItem[]
  >([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isEditModalOpen, setIsEditModalOpen] = useState(false);
  const [editingItem, setEditingItem] = useState<SavedVocabularyItem | null>(
    null
  );
  const { get, post, put, delete: apiDelete } = useApi();

  const fetchRecentVocabulary = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const params = new URLSearchParams();
      if (searchQuery) {
        params.append("search_query", searchQuery);
        params.append("limit", "100");
        params.append("precise", preciseSearch ? "true" : "false");
      } else {
        params.append("limit", "20");
      }
      const data: SavedVocabularyItem[] = await get<SavedVocabularyItem[]>(
        `/api/vocabulary?${params.toString()}`
      );
      setRecentVocabulary(data);
    } catch (err) {
      const errorMessage =
        err instanceof Error
          ? err.message
          : "Failed to fetch recent vocabulary";
      setError(errorMessage);
    } finally {
      setLoading(false);
    }
  }, [searchQuery, preciseSearch, get]);

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
      const updatedItem: SavedVocabularyItem = await put<SavedVocabularyItem>(
        `/api/vocabulary/${id}`,
        updates
      );
      setRecentVocabulary((prev) =>
        prev.map((item) => (item.id === id ? updatedItem : item))
      );
      closeEditModal();
    },
    [closeEditModal, put]
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
      setRecentVocabulary((prev) => prev.filter((item) => item.id !== id));
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
    error,
    refetch: fetchRecentVocabulary,
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
