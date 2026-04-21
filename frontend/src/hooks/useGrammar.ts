import { useState, useEffect, useRef, useCallback } from 'react';
import { API_BASE_URL } from '../config';

export interface CheatsheetInfo {
  filename: string;
  title: string;
  category: string;
}

interface CheatsheetContent {
  content: string;
}

export interface GrammarSearchResult {
  title: string;
  url: string;
  path: string;
}

interface UseGrammarReturn {
  cheatsheets: CheatsheetInfo[];
  selectedCheatsheet: CheatsheetContent | null;
  searchResults: GrammarSearchResult[];
  loading: boolean;
  error: string | null;
  searchLoading: boolean;
  searchError: string | null;
  fetchCheatsheets: () => Promise<void>;
  fetchCheatsheetContent: (filename: string) => Promise<void>;
  searchGrammar: (query: string, topK?: number) => Promise<void>;
  clearSearch: () => void;
}

const useGrammar = (): UseGrammarReturn => {
  const [cheatsheets, setCheatsheets] = useState<CheatsheetInfo[]>([]);
  const [selectedCheatsheet, setSelectedCheatsheet] = useState<CheatsheetContent | null>(null);
  const [searchResults, setSearchResults] = useState<GrammarSearchResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [searchLoading, setSearchLoading] = useState(false);
  const [searchError, setSearchError] = useState<string | null>(null);
  const hasFetchedRef = useRef(false);
  const latestSearchRequestRef = useRef(0);

  const fetchCheatsheets = useCallback(async () => {
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
  }, []);

  const fetchCheatsheetContent = useCallback(async (filename: string) => {
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
  }, []);

  const searchGrammar = useCallback(async (query: string, topK = 3) => {
    const requestId = latestSearchRequestRef.current + 1;
    latestSearchRequestRef.current = requestId;
    const trimmedQuery = query.trim();
    setSearchError(null);

    if (!trimmedQuery) {
      setSearchResults([]);
      return;
    }

    setSearchLoading(true);
    try {
      const params = new URLSearchParams({
        query: trimmedQuery,
        top_k: String(topK),
      });
      const response = await fetch(`${API_BASE_URL}/api/grammar/search?${params.toString()}`);
      if (!response.ok) {
        throw new Error(`Failed to search grammar cheatsheets: HTTP ${response.status}`);
      }
      const data: { results: GrammarSearchResult[] } = await response.json();
      if (requestId === latestSearchRequestRef.current) {
        setSearchResults(data.results);
      }
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to search grammar cheatsheets';
      if (requestId === latestSearchRequestRef.current) {
        setSearchResults([]);
        setSearchError(errorMessage);
      }
    } finally {
      if (requestId === latestSearchRequestRef.current) {
        setSearchLoading(false);
      }
    }
  }, []);

  const clearSearch = useCallback(() => {
    latestSearchRequestRef.current += 1;
    setSearchResults([]);
    setSearchError(null);
    setSearchLoading(false);
  }, []);

  useEffect(() => {
    if (!hasFetchedRef.current) {
      hasFetchedRef.current = true;
      fetchCheatsheets();
    }
  }, [fetchCheatsheets]);

  return {
    cheatsheets,
    selectedCheatsheet,
    searchResults,
    loading,
    error,
    searchLoading,
    searchError,
    fetchCheatsheets,
    fetchCheatsheetContent,
    searchGrammar,
    clearSearch,
  };
};

export default useGrammar;
