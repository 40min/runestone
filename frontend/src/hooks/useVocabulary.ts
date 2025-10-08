import { useState, useEffect, useRef, useCallback } from 'react';
import { API_BASE_URL } from '../config';

interface SavedVocabularyItem {
  id: number;
  user_id: number;
  word_phrase: string;
  translation: string;
  example_phrase: string | null;
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

  const fetchVocabulary = async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await fetch(`${API_BASE_URL}/api/vocabulary`);
      if (!response.ok) {
        throw new Error(`Failed to fetch vocabulary: HTTP ${response.status}`);
      }
      const data: SavedVocabularyItem[] = await response.json();
      setVocabulary(data);
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to fetch vocabulary';
      setError(errorMessage);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (!hasFetchedRef.current) {
      hasFetchedRef.current = true;
      fetchVocabulary();
    }
  }, []);

  return {
    vocabulary,
    loading,
    error,
    refetch: fetchVocabulary,
  };
};

export default useVocabulary;

export const useRecentVocabulary = (searchQuery?: string): UseRecentVocabularyReturn => {
  const [recentVocabulary, setRecentVocabulary] = useState<SavedVocabularyItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isEditModalOpen, setIsEditModalOpen] = useState(false);
  const [editingItem, setEditingItem] = useState<SavedVocabularyItem | null>(null);

  const fetchRecentVocabulary = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const params = new URLSearchParams();
      if (searchQuery) {
        params.append('search_query', searchQuery);
        params.append('limit', '100');
      } else {
        params.append('limit', '20');
      }
      const response = await fetch(`${API_BASE_URL}/api/vocabulary?${params.toString()}`);
      if (!response.ok) {
        throw new Error(`Failed to fetch recent vocabulary: HTTP ${response.status}`);
      }
      const data: SavedVocabularyItem[] = await response.json();
      setRecentVocabulary(data);
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to fetch recent vocabulary';
      setError(errorMessage);
    } finally {
      setLoading(false);
    }
  }, [searchQuery]);

  const openEditModal = useCallback((item: SavedVocabularyItem | null) => {
    setEditingItem(item);
    setIsEditModalOpen(true);
  }, []);

  const closeEditModal = useCallback(() => {
    setIsEditModalOpen(false);
    setEditingItem(null);
  }, []);

  const updateVocabularyItem = useCallback(async (id: number, updates: Partial<SavedVocabularyItem>) => {
    const response = await fetch(`${API_BASE_URL}/api/vocabulary/${id}`, {
      method: 'PUT',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(updates),
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      const errorMessage = errorData.detail || `Failed to update vocabulary item: HTTP ${response.status}`;
      throw new Error(errorMessage);
    }

    const updatedItem: SavedVocabularyItem = await response.json();
    setRecentVocabulary(prev => prev.map(item => item.id === id ? updatedItem : item));
    closeEditModal();
  }, [closeEditModal]);

  const createVocabularyItem = useCallback(async (item: Partial<SavedVocabularyItem>) => {
    const response = await fetch(`${API_BASE_URL}/api/vocabulary/item`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(item),
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      const errorMessage = errorData.detail || `Failed to create vocabulary item: HTTP ${response.status}`;
      throw new Error(errorMessage);
    }

    const newItem: SavedVocabularyItem = await response.json();
    setRecentVocabulary(prev => [newItem, ...prev]);
    closeEditModal();
  }, [closeEditModal]);

  const deleteVocabularyItem = useCallback(async (id: number) => {
    const response = await fetch(`${API_BASE_URL}/api/vocabulary/${id}`, {
      method: 'DELETE',
    });

    if (!response.ok) {
      throw new Error(`Failed to delete vocabulary item: HTTP ${response.status}`);
    }

    setRecentVocabulary(prev => prev.filter(item => item.id !== id));
    closeEditModal();
  }, [closeEditModal]);

  useEffect(() => {
    fetchRecentVocabulary();
  }, [searchQuery, fetchRecentVocabulary]);

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
  includeTranslation: boolean
): Promise<{ translation?: string; example_phrase: string }> => {
  const response = await fetch(`${API_BASE_URL}/api/vocabulary/improve`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      word_phrase: wordPhrase,
      include_translation: includeTranslation,
    }),
  });

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    const errorMessage = errorData.detail || `Failed to improve vocabulary item: HTTP ${response.status}`;
    throw new Error(errorMessage);
  }

  return response.json();
};
