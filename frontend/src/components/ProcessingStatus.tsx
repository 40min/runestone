import React from 'react';
import { LoadingSpinner } from './ui';

import type { ProcessingStep } from '../hooks/useImageProcessing';

interface ProcessingStatusProps {
  isProcessing: boolean;
  processingStep: ProcessingStep;
}

const ProcessingStatus: React.FC<ProcessingStatusProps> = ({ isProcessing, processingStep }) => {
  if (!isProcessing) return null;

  const getStatusMessage = () => {
    switch (processingStep) {
      case 'OCR':
        return 'Extracting text from image...';
      case 'ANALYZING':
        return 'Analyzing grammar and vocabulary...';
      default:
        return 'Processing...';
    }
  };

  return (
    <LoadingSpinner message={getStatusMessage()} />
  );
};

export default ProcessingStatus;
