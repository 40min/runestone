import { useState, useCallback, useRef } from "react";
import { useApi } from "../utils/api";

export type MemoryCategory = "personal_info" | "area_to_improve" | "knowledge_strength";

export interface MemoryItem {
  id: number;
  user_id: number;
  category: MemoryCategory;
  key: string;
  content: string;
  status: string;
  created_at: string;
  updated_at: string;
  status_changed_at: string | null;
  metadata_json: string | null;
}

export interface MemoryItemCreate {
  category: MemoryCategory;
  key: string;
  content: string;
  status?: string;
}

interface UseMemoryItemsReturn {
  items: MemoryItem[];
  loading: boolean;
  error: string | null;
  hasMore: boolean;
  fetchItems: (category?: MemoryCategory, status?: string, reset?: boolean) => Promise<void>;
  createItem: (data: MemoryItemCreate) => Promise<MemoryItem>;
  updateStatus: (id: number, status: string) => Promise<MemoryItem>;
  promoteItem: (id: number, category: MemoryCategory, status?: string) => Promise<MemoryItem>;
  deleteItem: (id: number) => Promise<void>;
  clearCategory: (category: MemoryCategory) => Promise<void>;
}

const useMemoryItems = (): UseMemoryItemsReturn => {
  const [items, setItems] = useState<MemoryItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [hasMore, setHasMore] = useState(true);
  const offsetRef = useRef(0);
  const { get, post, put, delete: apiDelete } = useApi();

  const LIMIT = 100;

  const fetchItems = useCallback(
    async (category?: MemoryCategory, status?: string, reset = false) => {
      setLoading(true);
      setError(null);

      const currentOffset = reset ? 0 : offsetRef.current;

      try {
        const params = new URLSearchParams();
        if (category) params.append("category", category);
        if (status) params.append("status", status);
        params.append("limit", LIMIT.toString());
        params.append("offset", currentOffset.toString());

        const data = await get<MemoryItem[]>(`/api/memory?${params.toString()}`);

        if (reset) {
          setItems(data);
          offsetRef.current = data.length;
        } else {
          setItems((prev) => [...prev, ...data]);
          offsetRef.current += data.length;
        }

        setHasMore(data.length === LIMIT);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to fetch memory items");
      } finally {
        setLoading(false);
      }
    },
    [get]
  );

  const createItem = useCallback(
    async (data: MemoryItemCreate) => {
      try {
        const newItem = await post<MemoryItem>("/api/memory", data);
        setItems((prev) => {
          const index = prev.findIndex((item) => item.category === newItem.category && item.key === newItem.key);
          if (index !== -1) {
            const newItems = [...prev];
            newItems[index] = newItem;
            return newItems;
          }
          return [newItem, ...prev];
        });
        return newItem;
      } catch (err) {
        throw err instanceof Error ? err : new Error("Failed to create memory item");
      }
    },
    [post]
  );

  const updateStatus = useCallback(
    async (id: number, status: string) => {
      try {
        const updatedItem = await put<MemoryItem>(`/api/memory/${id}/status`, { status });
        setItems((prev) => prev.map((item) => (item.id === id ? updatedItem : item)));
        return updatedItem;
      } catch (err) {
        throw err instanceof Error ? err : new Error("Failed to update status");
      }
    },
    [put]
  );

  const promoteItem = useCallback(
    async (id: number, category: MemoryCategory, status?: string) => {
      try {
        const promotedItem = await post<MemoryItem>(`/api/memory/${id}/promote`, {});
        await fetchItems(category, status, true);
        return promotedItem;
      } catch (err) {
        throw err instanceof Error ? err : new Error("Failed to promote item");
      }
    },
    [post, fetchItems]
  );

  const deleteItem = useCallback(
    async (id: number) => {
      try {
        await apiDelete(`/api/memory/${id}`);
        setItems((prev) => prev.filter((item) => item.id !== id));
      } catch (err) {
        throw err instanceof Error ? err : new Error("Failed to delete item");
      }
    },
    [apiDelete]
  );

  const clearCategory = useCallback(
    async (category: MemoryCategory) => {
      try {
        await apiDelete(`/api/memory?category=${category}`);
        setItems((prev) => prev.filter((item) => item.category !== category));
      } catch (err) {
        throw err instanceof Error ? err : new Error("Failed to clear category");
      }
    },
    [apiDelete]
  );

  return {
    items,
    loading,
    error,
    hasMore,
    fetchItems,
    createItem,
    updateStatus,
    promoteItem,
    deleteItem,
    clearCategory,
  };
};

export default useMemoryItems;
