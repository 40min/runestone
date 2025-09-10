import React from 'react';

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
    <div className="flex flex-col items-center justify-center gap-4 py-8">
      <div className="relative w-16 h-16">
        <div
          className="w-16 h-16 border-4 border-[#4d3c63] border-t-[var(--primary-color)] rounded-full animate-spin"
          role="status"
          aria-label="Processing"
        />
      </div>
      <p className="text-lg font-semibold text-white">
        {getStatusMessage()}
      </p>
    </div>
  );
};

export default ProcessingStatus;