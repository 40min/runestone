import { useState, useEffect, useRef, useCallback } from 'react';
import { API_BASE_URL } from '../config';
import { useApi } from '../utils/api';
import type { VocabularyImprovementMode } from '../constants';

interface SavedVocabularyItem {
  id: number;
  user_id: number;
  word_phrase: string;
  translation: string;
  example_phrase: string | null;
  extra_info: string | null;
  in_learn: boolean;
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
  updateVocabularyItem: (id: number, updates: Partial<SavedVocabularyItem>) => Promise<void>;
  createVocabularyItem: (item: Partial<SavedVocabularyItem>) => Promise<void>;
  deleteVocabularyItem: (id: number) => Promise<void>;
}

const useVocabulary = (): UseVocabularyReturn => {
  const [vocabulary, setVocabulary] = useState<SavedVocabularyItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const hasFetchedRef = useRef(false);
  const api = useApi();

  const fetchVocabulary = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data: SavedVocabularyItem[] = await api<SavedVocabularyItem[]>('/api/vocabulary');
      setVocabulary(data);
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to fetch vocabulary';
      setError(errorMessage);
    } finally {
      setLoading(false);
    }
  }, [api]);

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

export const useRecentVocabulary = (searchQuery?: string, preciseSearch = false): UseRecentVocabularyReturn => {
  const [recentVocabulary, setRecentVocabulary] = useState<SavedVocabularyItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isEditModalOpen, setIsEditModalOpen] = useState(false);
  const [editingItem, setEditingItem] = useState<SavedVocabularyItem | null>(null);
  const api = useApi();

  const fetchRecentVocabulary = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const params = new URLSearchParams();
      if (searchQuery) {
        params.append('search_query', searchQuery);
        params.append('limit', '100');
        params.append('precise', preciseSearch ? 'true' : 'false');
      } else {
        params.append('limit', '20');
      }
      const data: SavedVocabularyItem[] = await api<SavedVocabularyItem[]>(`/api/vocabulary?${params.toString()}`);
      setRecentVocabulary(data);
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to fetch recent vocabulary';
      setError(errorMessage);
    } finally {
      setLoading(false);
    }
  }, [searchQuery, preciseSearch, api]);

  const openEditModal = useCallback((item: SavedVocabularyItem | null) => {
    setEditingItem(item);
    setIsEditModalOpen(true);
  }, []);

  const closeEditModal = useCallback(() => {
    setIsEditModalOpen(false);
    setEditingItem(null);
  }, []);

  const updateVocabularyItem = useCallback(async (id: number, updates: Partial<SavedVocabularyItem>) => {
    const updatedItem: SavedVocabularyItem = await api<SavedVocabularyItem>(`/api/vocabulary/${id}`, {
      method: 'PUT',
      body: updates,
    });
    setRecentVocabulary(prev => prev.map(item => item.id === id ? updatedItem : item));
    closeEditModal();
  }, [closeEditModal, api]);

  const createVocabularyItem = useCallback(async (item: Partial<SavedVocabularyItem>) => {
    const newItem: SavedVocabularyItem = await api<SavedVocabularyItem>('/api/vocabulary/item', {
      method: 'POST',
      body: item,
    });
    setRecentVocabulary(prev => [newItem, ...prev]);
    closeEditModal();
  }, [closeEditModal, api]);

  const deleteVocabularyItem = useCallback(async (id: number) => {
    await api(`/api/vocabulary/${id}`, {
      method: 'DELETE',
    });
    setRecentVocabulary(prev => prev.filter(item => item.id !== id));
    closeEditModal();
  }, [closeEditModal, api]);

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
  wordPhrase: string,
  mode: VocabularyImprovementMode
): Promise<{ translation?: string; example_phrase?: string; extra_info?: string }> => {
  // Note: This function doesn't use useApi because it's not a hook
  // and doesn't have access to authentication context
  const response = await fetch(`${API_BASE_URL}/api/vocabulary/improve`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      word_phrase: wordPhrase,
      mode: mode,
    }),
  });

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    const errorMessage = errorData.detail || `Failed to improve vocabulary item: HTTP ${response.status}`;
    throw new Error(errorMessage);
  }

  return response.json();
};
