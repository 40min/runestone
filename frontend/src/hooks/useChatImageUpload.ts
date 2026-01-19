import { useState, useCallback } from 'react';
import { useApi } from '../utils/api';
import { useAuth } from '../context/AuthContext';

interface UploadedImage {
  id: string;
  url: string;
}

interface UseChatImageUploadReturn {
  uploadedImages: UploadedImage[];
  uploadImage: (file: File) => Promise<string | null>;
  isUploading: boolean;
  error: string | null;
  clearError: () => void;
}

const MAX_IMAGES = 3;

export const useChatImageUpload = (): UseChatImageUploadReturn => {
  const [uploadedImages, setUploadedImages] = useState<UploadedImage[]>([]);
  const [isUploading, setIsUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const { post } = useApi();
  const { token } = useAuth();

  const uploadImage = useCallback(
    async (file: File): Promise<string | null> => {
      if (!token) {
        setError('Authentication required');
        return null;
      }

      setIsUploading(true);
      setError(null);

      try {
        // Create FormData for multipart upload
        const formData = new FormData();
        formData.append('file', file);

        // Upload to backend using the updated useApi which supports FormData
        const data = await post<{ message: string }>('/api/chat/image', formData);
        const translationMessage = data.message;

        // Create image URL for sidebar
        const imageUrl = URL.createObjectURL(file);
        const newImage: UploadedImage = {
          id: crypto.randomUUID(),
          url: imageUrl,
        };

        // Update images with FIFO behavior (max 3)
        setUploadedImages((prev) => {
          const updated = [...prev, newImage];
          // Keep only the 3 most recent
          return updated.slice(-MAX_IMAGES);
        });

        return translationMessage;
      } catch (err) {
        const errorMessage = err instanceof Error ? err.message : 'Failed to process image';
        setError(errorMessage);
        return null;
      } finally {
        setIsUploading(false);
      }
    },
    [token, post]
  );

  const clearError = useCallback(() => {
    setError(null);
  }, []);

  return {
    uploadedImages,
    uploadImage,
    isUploading,
    error,
    clearError,
  };
};
