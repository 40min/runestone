import { useState } from 'react';

interface OCRResult {
  text: string;
  character_count: number;
}

interface GrammarFocus {
  topic: string;
  explanation: string;
  has_explicit_rules: boolean;
}

interface VocabularyItem {
  swedish: string;
  english: string;
}

interface ContentAnalysis {
  grammar_focus: GrammarFocus;
  vocabulary: VocabularyItem[];
}

interface ProcessingResult {
  ocr_result: OCRResult;
  analysis: ContentAnalysis;
  extra_info?: string;
  processing_successful: boolean;
}

interface UseImageProcessingReturn {
  processImage: (file: File) => Promise<void>;
  result: ProcessingResult | null;
  error: string | null;
  isProcessing: boolean;
  reset: () => void;
  currentImage: string | null;
  progress: number;
}

const useImageProcessing = (): UseImageProcessingReturn => {
  const [result, setResult] = useState<ProcessingResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isProcessing, setIsProcessing] = useState(false);
  const [currentImage, setCurrentImage] = useState<string | null>(null);
  const [progress, setProgress] = useState(0);

  const processImage = async (file: File) => {
    setIsProcessing(true);
    setError(null);
    setResult(null);
    setProgress(10);

    // Create data URL for the image to display during processing
    const imageUrl = URL.createObjectURL(file);
    setCurrentImage(imageUrl);
    setProgress(20);

    try {
      setProgress(40);
      const formData = new FormData();
      formData.append('file', file);

      setProgress(60);
      const response = await fetch('http://localhost:8010/api/process', {
        method: 'POST',
        body: formData,
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ error: 'Unknown error' }));
        throw new Error(errorData.error || `HTTP ${response.status}: ${response.statusText}`);
      }

      setProgress(80);
      const data: ProcessingResult = await response.json();
      setResult(data);
      setProgress(100);
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'An unexpected error occurred';
      setError(errorMessage);
    } finally {
      setIsProcessing(false);
      // Clean up the object URL to prevent memory leaks
      if (imageUrl) {
        URL.revokeObjectURL(imageUrl);
        setCurrentImage(null);
      }
    }
  };

  const reset = () => {
    setResult(null);
    setError(null);
    setIsProcessing(false);
    setProgress(0);
  };

  return {
    processImage,
    result,
    error,
    isProcessing,
    reset,
    progress,
    currentImage,
  };
};

export default useImageProcessing;