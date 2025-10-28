import { useState, useEffect, useRef } from 'react';
import { API_BASE_URL } from '../config';

interface CheatsheetInfo {
  filename: string;
  title: string;
  category: string;
}

interface CheatsheetContent {
  content: string;
}

interface UseGrammarReturn {
  cheatsheets: CheatsheetInfo[];
  selectedCheatsheet: CheatsheetContent | null;
  loading: boolean;
  error: string | null;
  fetchCheatsheets: () => Promise<void>;
  fetchCheatsheetContent: (filename: string) => Promise<void>;
}

const useGrammar = (): UseGrammarReturn => {
  const [cheatsheets, setCheatsheets] = useState<CheatsheetInfo[]>([]);
  const [selectedCheatsheet, setSelectedCheatsheet] = useState<CheatsheetContent | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const hasFetchedRef = useRef(false);

  const fetchCheatsheets = async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await fetch(`${API_BASE_URL}/api/grammar/cheatsheets`);
      if (!response.ok) {
        throw new Error(`Failed to fetch cheatsheets: HTTP ${response.status}`);
      }
      const data: CheatsheetInfo[] = await response.json();
      setCheatsheets(data);
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to fetch cheatsheets';
      setError(errorMessage);
    } finally {
      setLoading(false);
    }
  };

  const fetchCheatsheetContent = async (filename: string) => {
    setLoading(true);
    setError(null);
    try {
      const response = await fetch(`${API_BASE_URL}/api/grammar/cheatsheets/${filename}`);
      if (!response.ok) {
        throw new Error(`Failed to fetch cheatsheet content: HTTP ${response.status}`);
      }
      const data: CheatsheetContent = await response.json();
      setSelectedCheatsheet(data);
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to fetch cheatsheet content';
      setError(errorMessage);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (!hasFetchedRef.current) {
      hasFetchedRef.current = true;
      fetchCheatsheets();
    }
  }, []);

  return {
    cheatsheets,
    selectedCheatsheet,
    loading,
    error,
    fetchCheatsheets,
    fetchCheatsheetContent,
  };
};

export default useGrammar;
