import { useState } from "react";
import { API_BASE_URL } from "../config";
import { useApi } from "../utils/api";
import { useAuth } from "../context/AuthContext";

export interface OCRResult {
  text: string;
  character_count: number;
}

export interface GrammarFocus {
  topic: string;
  explanation: string;
  has_explicit_rules: boolean;
  rules?: string;
}

export interface VocabularyItem {
  id?: string;
  swedish: string;
  english: string;
  example_phrase?: string;
  extra_info?: string;
  known?: boolean;
}

export interface EnrichedVocabularyItem extends VocabularyItem {
  id: string;
  [key: string]: unknown; // Add index signature
}

export interface ContentAnalysis {
  grammar_focus: GrammarFocus;
  vocabulary: VocabularyItem[];
  core_topics: string[];
}

export type ProcessingStep = "IDLE" | "OCR" | "ANALYZING" | "DONE";

interface UseImageProcessingReturn {
  processImage: (file: File, recognizeOnly: boolean) => Promise<void>;
  recognizeImage: (file: File) => Promise<OCRResult | null>;
  analyzeText: (text: string) => Promise<void>;
  saveVocabulary: (vocabulary: EnrichedVocabularyItem[], enrich: boolean) => Promise<void>;
  onVocabularyUpdated: (updatedVocabulary: EnrichedVocabularyItem[]) => void;
  ocrResult: OCRResult | null;
  analysisResult: ContentAnalysis | null;
  processingStep: ProcessingStep;
  error: string | null;
  isProcessing: boolean;
  reset: () => void;
  currentImage: string | null;
  progress: number;
}

const useImageProcessing = (): UseImageProcessingReturn => {
  const [ocrResult, setOcrResult] = useState<OCRResult | null>(null);
  const [analysisResult, setAnalysisResult] = useState<ContentAnalysis | null>(
    null
  );
  const [processingStep, setProcessingStep] = useState<ProcessingStep>("IDLE");
  const [error, setError] = useState<string | null>(null);
  const [isProcessing, setIsProcessing] = useState(false);
  const [currentImage, setCurrentImage] = useState<string | null>(null);
  const [progress, setProgress] = useState(0);
  const { post } = useApi();
  const { token, logout } = useAuth();

  const reset = () => {
    setOcrResult(null);
    setAnalysisResult(null);
    setProcessingStep("IDLE");
    setError(null);
    setIsProcessing(false);
    setProgress(0);
    setCurrentImage(null);
  };

  const recognizeImage = async (file: File): Promise<OCRResult | null> => {
    setIsProcessing(true);
    setError(null);
    setOcrResult(null);
    setProcessingStep("IDLE");
    setProgress(10);

    const imageUrl = URL.createObjectURL(file);
    setCurrentImage(imageUrl);
    setProgress(20);

    try {
      setProcessingStep("OCR");
      setProgress(30);
      const formData = new FormData();
      formData.append("file", file);

      const url = `${API_BASE_URL}/api/ocr`;
      const headers: Record<string, string> = {};
      if (token) {
        headers['Authorization'] = `Bearer ${token}`;
      }

      const response = await fetch(url, {
        method: "POST",
        body: formData,
        headers,
      });

      if (!response.ok) {
        if (response.status === 401) {
          logout();
        }
        const errorData = await response
          .json()
          .catch(() => ({ error: "Unknown error" }));
        throw new Error(
          errorData.error ||
            `OCR failed: HTTP ${response.status}: ${response.statusText}`
        );
      }

      const ocrData: OCRResult = await response.json();
      setOcrResult(ocrData);
      setProgress(50);
      setProcessingStep("DONE");
      setIsProcessing(false);
      return ocrData;
    } catch (err) {
      const errorMessage =
        err instanceof Error ? err.message : "An unexpected error occurred during OCR";
      setError(errorMessage);
      setProcessingStep("IDLE");
      setIsProcessing(false);
      return null;
    }
  };

  const analyzeText = async (text: string): Promise<void> => {
    setIsProcessing(true);
    setError(null);
    setAnalysisResult(null);
    setProcessingStep("IDLE");
    setProgress(0);

    try {
      setProcessingStep("ANALYZING");
      setProgress(60);
      const analysisData: ContentAnalysis = await post<ContentAnalysis>('/api/analyze', { text });
      setAnalysisResult(analysisData);
      setProgress(100);
      setProcessingStep("DONE");
    } catch (err) {
      const errorMessage =
        err instanceof Error ? err.message : "An unexpected error occurred during analysis";
      setError(errorMessage);
      setProcessingStep("IDLE");
    } finally {
      setIsProcessing(false);
      setCurrentImage(null);
    }
  };

  const processImage = async (file: File, recognizeOnly: boolean) => {
    setError(null);
    setAnalysisResult(null);
    setProcessingStep("IDLE");
    setProgress(0);

    try {
      const ocrData = await recognizeImage(file);
      if (ocrData && ocrData.text) {
        if (!recognizeOnly) {
          await analyzeText(ocrData.text);
        }
      }
    } catch (err) {
      const errorMessage =
        err instanceof Error ? err.message : "An unexpected error occurred during image processing";
      setError(errorMessage);
    }
  };

  const saveVocabulary = async (vocabulary: EnrichedVocabularyItem[], enrich: boolean = true) => {
    try {
      const transformedItems = vocabulary.map((item) => ({
        word_phrase: item.swedish,
        translation: item.english,
        example_phrase: item.example_phrase,
      }));

      await post('/api/vocabulary', { items: transformedItems, enrich });
    } catch (err) {
      const errorMessage =
        err instanceof Error ? err.message : "Failed to save vocabulary";
      throw new Error(errorMessage);
    }
  };

  const onVocabularyUpdated = (updatedVocabulary: EnrichedVocabularyItem[]) => {
    setAnalysisResult((prev) => {
      if (!prev) return null;
      return {
        ...prev,
        vocabulary: updatedVocabulary,
      };
    });
  };

  return {
    processImage,
    recognizeImage,
    analyzeText,
    saveVocabulary,
    onVocabularyUpdated,
    ocrResult,
    analysisResult,
    processingStep,
    error,
    isProcessing,
    reset,
    progress,
    currentImage,
  };
};

export default useImageProcessing;
