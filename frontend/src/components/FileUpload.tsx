import React, { useState, useRef } from 'react';

interface FileUploadProps {
  onFileSelect: (file: File) => void;
  isProcessing: boolean;
}

const FileUpload: React.FC<FileUploadProps> = ({ onFileSelect, isProcessing }) => {
  const [dragActive, setDragActive] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleDrag = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === "dragenter" || e.type === "dragover") {
      setDragActive(true);
    } else if (e.type === "dragleave") {
      setDragActive(false);
    }
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);

    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      const file = e.dataTransfer.files[0];
      handleFileSelect(file);
    }
  };

  const handleFileSelect = (file: File) => {
    if (file.type.startsWith('image/')) {
      onFileSelect(file);
    } else {
      alert('Please select an image file');
    }
  };

  const handleFileInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      handleFileSelect(e.target.files[0]);
    }
  };

  const handleButtonClick = () => {
    fileInputRef.current?.click();
  };

  return (
    <div className="rounded-lg border-2 border-dashed border-[#4d3c63] p-12 text-center hover:border-[var(--primary-color)] transition-colors">
      <div className="flex flex-col items-center gap-4">
        <span className="material-symbols-outlined text-6xl text-gray-500">upload_file</span>
        <p className="text-lg font-semibold text-white">Drag & drop a file or click to upload</p>
        <p className="text-sm text-gray-400">PNG, JPG, or GIF up to 10MB</p>
        <button
          type="button"
          onClick={handleButtonClick}
          className="mt-4 flex min-w-[120px] cursor-pointer items-center justify-center overflow-hidden rounded-md h-12 px-6 bg-[var(--primary-color)] text-[#111714] text-base font-bold leading-normal tracking-[0.015em] hover:bg-opacity-90 transition-all"
          disabled={isProcessing}
        >
          <span className="truncate">Browse Files</span>
        </button>
        <input
          ref={fileInputRef}
          type="file"
          accept="image/*"
          onChange={handleFileInputChange}
          className="hidden"
          disabled={isProcessing}
        />
      </div>
    </div>
  );
};

export default FileUpload;