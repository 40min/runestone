import { useState, useEffect, useRef, useCallback } from 'react';
import { API_BASE_URL } from '../config';

interface SavedVocabularyItem {
  id: number;
  user_id: number;
  word_phrase: string;
  translation: string;
  example_phrase: string | null;
  in_learn: boolean;
  showed_times: number;
  created_at: string;
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

  useEffect(() => {
    fetchRecentVocabulary();
  }, [searchQuery, fetchRecentVocabulary]);

  return {
    recentVocabulary,
    loading,
    error,
    refetch: fetchRecentVocabulary,
  };
};