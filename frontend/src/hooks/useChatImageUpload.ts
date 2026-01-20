import { useState, useCallback, useEffect, useRef } from 'react';
import { useApi } from '../utils/api';
import { useAuth } from '../context/AuthContext';
import { generateId } from '../utils/id';

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
  clearImages: () => void;
}

const MAX_IMAGES = 3;

export const useChatImageUpload = (): UseChatImageUploadReturn => {
  const [uploadedImages, setUploadedImages] = useState<UploadedImage[]>([]);
  const [isUploading, setIsUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const { post } = useApi();
  const { token } = useAuth();

  // Keep track of current images for cleanup on unmount
  const imagesRef = useRef<UploadedImage[]>([]);
  useEffect(() => {
    imagesRef.current = uploadedImages;
  }, [uploadedImages]);

  // Cleanup all object URLs on unmount
  useEffect(() => {
    return () => {
      imagesRef.current.forEach((img) => URL.revokeObjectURL(img.url));
    };
  }, []);

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
          id: generateId(),
          url: imageUrl,
        };

        // Update images with FIFO behavior (max 3)
        setUploadedImages((prev) => {
          const updated = [...prev, newImage];
          // Keep only the 3 most recent, revoking any that are removed
          if (updated.length > MAX_IMAGES) {
            const removed = updated.shift();
            if (removed) {
              URL.revokeObjectURL(removed.url);
            }
          }
          return updated;
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

  const clearImages = useCallback(() => {
    // Revoke all current URLs before clearing
    uploadedImages.forEach((img) => URL.revokeObjectURL(img.url));
    setUploadedImages([]);
  }, [uploadedImages]);

  return {
    uploadedImages,
    uploadImage,
    isUploading,
    error,
    clearError,
    clearImages,
  };
};
