import { useState } from 'react';
import { API_BASE_URL } from '../config';

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

interface UseImageProcessingReturn {
  processImage: (file: File) => Promise<void>;
  ocrResult: OCRResult | null;
  analysisResult: ContentAnalysis | null;
  resourcesResult: string | null;
  processingStep: 'IDLE' | 'OCR' | 'ANALYZING' | 'RESOURCES' | 'DONE';
  error: string | null;
  isProcessing: boolean;
  reset: () => void;
  currentImage: string | null;
  progress: number;
}

const useImageProcessing = (): UseImageProcessingReturn => {
  const [ocrResult, setOcrResult] = useState<OCRResult | null>(null);
  const [analysisResult, setAnalysisResult] = useState<ContentAnalysis | null>(null);
  const [resourcesResult, setResourcesResult] = useState<string | null>(null);
  const [processingStep, setProcessingStep] = useState<'IDLE' | 'OCR' | 'ANALYZING' | 'RESOURCES' | 'DONE'>('IDLE');
  const [error, setError] = useState<string | null>(null);
  const [isProcessing, setIsProcessing] = useState(false);
  const [currentImage, setCurrentImage] = useState<string | null>(null);
  const [progress, setProgress] = useState(0);

  const processImage = async (file: File) => {
    setIsProcessing(true);
    setError(null);
    setOcrResult(null);
    setAnalysisResult(null);
    setResourcesResult(null);
    setProcessingStep('IDLE');
    setProgress(10);

    // Create data URL for the image to display during processing
    const imageUrl = URL.createObjectURL(file);
    setCurrentImage(imageUrl);
    setProgress(20);

    try {
      // Step 1: OCR
      setProcessingStep('OCR');
      setProgress(30);
      const formData = new FormData();
      formData.append('file', file);

      const ocrResponse = await fetch(`${API_BASE_URL}/api/ocr`, {
        method: 'POST',
        body: formData,
      });

      if (!ocrResponse.ok) {
        const errorData = await ocrResponse.json().catch(() => ({ error: 'Unknown error' }));
        throw new Error(errorData.error || `OCR failed: HTTP ${ocrResponse.status}: ${ocrResponse.statusText}`);
      }

      const ocrData: OCRResult = await ocrResponse.json();
      setOcrResult(ocrData);
      setProgress(50);

      // Step 2: Analysis
      setProcessingStep('ANALYZING');
      setProgress(60);
      const analyzeResponse = await fetch(`${API_BASE_URL}/api/analyze`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ text: ocrData.text }),
      });

      if (!analyzeResponse.ok) {
        const errorData = await analyzeResponse.json().catch(() => ({ error: 'Unknown error' }));
        throw new Error(errorData.error || `Analysis failed: HTTP ${analyzeResponse.status}: ${analyzeResponse.statusText}`);
      }

      const analysisData: ContentAnalysis = await analyzeResponse.json();
      setAnalysisResult(analysisData);
      setProgress(80);

      // Step 3: Resources
      setProcessingStep('RESOURCES');
      setProgress(90);
      const resourcesResponse = await fetch(`${API_BASE_URL}/api/resources`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ analysis: analysisData }),
      });

      if (!resourcesResponse.ok) {
        const errorData = await resourcesResponse.json().catch(() => ({ error: 'Unknown error' }));
        throw new Error(errorData.error || `Resources failed: HTTP ${resourcesResponse.status}: ${resourcesResponse.statusText}`);
      }

      const resourcesData = await resourcesResponse.json();
      setResourcesResult(resourcesData.extra_info);
      setProgress(100);
      setProcessingStep('DONE');

    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'An unexpected error occurred';
      setError(errorMessage);
      setProcessingStep('IDLE');
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
    setOcrResult(null);
    setAnalysisResult(null);
    setResourcesResult(null);
    setProcessingStep('IDLE');
    setError(null);
    setIsProcessing(false);
    setProgress(0);
  };

  return {
    processImage,
    ocrResult,
    analysisResult,
    resourcesResult,
    processingStep,
    error,
    isProcessing,
    reset,
    progress,
    currentImage,
  };
};

export default useImageProcessing;