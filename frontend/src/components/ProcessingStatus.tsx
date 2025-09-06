import React from 'react';

interface ProcessingStatusProps {
  isProcessing: boolean;
  progress?: number;
}

const ProcessingStatus: React.FC<ProcessingStatusProps> = ({ isProcessing, progress }) => {
  return (
    <div className="space-y-6">
      <h3 className="text-2xl font-bold text-white">Processing Status</h3>
      <div className="space-y-3">
        <div className="flex justify-between text-sm font-medium text-gray-300">
          <p>Analyzing...</p>
          <p>{progress}%</p>
        </div>
        <div className="w-full bg-[#4d3c63] rounded-full h-2.5">
          <div
            className="bg-[var(--primary-color)] h-2.5 rounded-full transition-all duration-300"
            style={{ width: `${progress}%` }}
          ></div>
        </div>
      </div>
    </div>
  );
};

export default ProcessingStatus;