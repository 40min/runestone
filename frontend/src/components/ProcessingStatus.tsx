import React from 'react';
import { LoadingSpinner } from './ui';

interface ProcessingStatusProps {
  isProcessing: boolean;
  processingStep: 'IDLE' | 'OCR' | 'ANALYZING' | 'RESOURCES' | 'DONE';
}

const ProcessingStatus: React.FC<ProcessingStatusProps> = ({ isProcessing, processingStep }) => {
  if (!isProcessing) return null;

  const getStatusMessage = () => {
    switch (processingStep) {
      case 'OCR':
        return 'Extracting text from image...';
      case 'ANALYZING':
        return 'Analyzing grammar and vocabulary...';
      case 'RESOURCES':
        return 'Finding additional resources...';
      default:
        return 'Processing...';
    }
  };

  return (
    <LoadingSpinner message={getStatusMessage()} />
  );
};

export default ProcessingStatus;
