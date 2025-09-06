import React from 'react';

interface ProcessingStatusProps {
  isProcessing: boolean;
}

const ProcessingStatus: React.FC<ProcessingStatusProps> = ({ isProcessing }) => {
  if (!isProcessing) return null;

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
        Processing...
      </p>
    </div>
  );
};

export default ProcessingStatus;