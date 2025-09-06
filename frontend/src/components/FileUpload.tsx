import React, { useState, useRef, useEffect } from "react";

interface FileUploadProps {
  onFileSelect: (file: File) => void;
  isProcessing: boolean;
}

const FileUpload: React.FC<FileUploadProps> = ({
  onFileSelect,
  isProcessing,
}) => {
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [isZoomed, setIsZoomed] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleFileSelect = (file: File) => {
    if (file.type.startsWith("image/")) {
      setSelectedFile(file);
      setPreviewUrl(URL.createObjectURL(file));
      onFileSelect(file);
    } else {
      alert("Please select an image file");
    }
  };

  useEffect(() => {
    return () => {
      if (previewUrl && typeof URL !== "undefined" && URL.revokeObjectURL) {
        URL.revokeObjectURL(previewUrl);
      }
    };
  }, [previewUrl]);

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
        {selectedFile && previewUrl ? (
          <>
            <img
              src={previewUrl}
              alt="Preview"
              className={`max-w-full ${
                isZoomed ? "max-h-screen" : "max-h-96"
              } object-contain rounded-lg cursor-pointer transition-all duration-300`}
              onClick={() => setIsZoomed(!isZoomed)}
            />
            <p className="text-lg font-semibold text-white">
              {selectedFile.name}
            </p>
          </>
        ) : (
          <>
            <span className="material-symbols-outlined text-6xl text-gray-500">
              upload_file
            </span>
            <p className="text-lg font-semibold text-white">
              Drag & drop a file or click to upload
            </p>
            <p className="text-sm text-gray-400">PNG, JPG, or GIF up to 10MB</p>
          </>
        )}
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
