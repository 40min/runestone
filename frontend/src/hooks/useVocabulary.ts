import { useState, useEffect, useRef } from 'react';
import { API_BASE_URL } from '../config';

interface SavedVocabularyItem {
  id: number;
  user_id: number;
  word_phrase: string;
  translation: string;
  example_phrase: string | null;
  created_at: string;
}

interface UseVocabularyReturn {
  vocabulary: SavedVocabularyItem[];
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