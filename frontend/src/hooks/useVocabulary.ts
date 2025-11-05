import { useState, useEffect, useRef, useCallback } from 'react';
import { API_BASE_URL } from '../config';
import { useAuth } from '../context/AuthContext';
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
  const { token, logout } = useAuth();

  const fetchVocabulary = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const headers: Record<string, string> = {};
      if (token) {
        headers['Authorization'] = `Bearer ${token}`;
      }

      const response = await fetch(`${API_BASE_URL}/api/vocabulary`, {
        ...(Object.keys(headers).length > 0 ? { headers } : {}),
      });
      if (!response.ok) {
        if (response.status === 401) {
          logout();
          return;
        }
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
  }, [token, logout]);

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
  const { token, logout } = useAuth();

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
      const headers: Record<string, string> = {};
      if (token) {
        headers['Authorization'] = `Bearer ${token}`;
      }

      const response = await fetch(`${API_BASE_URL}/api/vocabulary?${params.toString()}`, {
        ...(Object.keys(headers).length > 0 ? { headers } : {}),
      });
      if (!response.ok) {
        if (response.status === 401) {
          logout();
          return;
        }
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
  }, [searchQuery, preciseSearch, token, logout]);

  const openEditModal = useCallback((item: SavedVocabularyItem | null) => {
    setEditingItem(item);
    setIsEditModalOpen(true);
  }, []);

  const closeEditModal = useCallback(() => {
    setIsEditModalOpen(false);
    setEditingItem(null);
  }, []);

  const updateVocabularyItem = useCallback(async (id: number, updates: Partial<SavedVocabularyItem>) => {
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
    };
    if (token) {
      headers['Authorization'] = `Bearer ${token}`;
    }

    const response = await fetch(`${API_BASE_URL}/api/vocabulary/${id}`, {
      method: 'PUT',
      ...(Object.keys(headers).length > 0 ? { headers } : { 'Content-Type': 'application/json' }),
      body: JSON.stringify(updates),
    });

    if (!response.ok) {
      if (response.status === 401) {
        logout();
        return;
      }
      const errorData = await response.json().catch(() => ({}));
      const errorMessage = errorData.detail || `Failed to update vocabulary item: HTTP ${response.status}`;
      throw new Error(errorMessage);
    }

    const updatedItem: SavedVocabularyItem = await response.json();
    setRecentVocabulary(prev => prev.map(item => item.id === id ? updatedItem : item));
    closeEditModal();
  }, [closeEditModal, token, logout]);

  const createVocabularyItem = useCallback(async (item: Partial<SavedVocabularyItem>) => {
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
    };
    if (token) {
      headers['Authorization'] = `Bearer ${token}`;
    }

    const response = await fetch(`${API_BASE_URL}/api/vocabulary/item`, {
      method: 'POST',
      ...(Object.keys(headers).length > 0 ? { headers } : { 'Content-Type': 'application/json' }),
      body: JSON.stringify(item),
    });

    if (!response.ok) {
      if (response.status === 401) {
        logout();
        return;
      }
      const errorData = await response.json().catch(() => ({}));
      const errorMessage = errorData.detail || `Failed to create vocabulary item: HTTP ${response.status}`;
      throw new Error(errorMessage);
    }

    const newItem: SavedVocabularyItem = await response.json();
    setRecentVocabulary(prev => [newItem, ...prev]);
    closeEditModal();
  }, [closeEditModal, token, logout]);

  const deleteVocabularyItem = useCallback(async (id: number) => {
    const headers: Record<string, string> = {};
    if (token) {
      headers['Authorization'] = `Bearer ${token}`;
    }

    const response = await fetch(`${API_BASE_URL}/api/vocabulary/${id}`, {
      method: 'DELETE',
      ...(Object.keys(headers).length > 0 ? { headers } : {}),
    });

    if (!response.ok) {
      if (response.status === 401) {
        logout();
        return;
      }
      throw new Error(`Failed to delete vocabulary item: HTTP ${response.status}`);
    }

    setRecentVocabulary(prev => prev.filter(item => item.id !== id));
    closeEditModal();
  }, [closeEditModal, token, logout]);

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
