import React, { useState, useRef, useEffect } from "react";
import { Button, Box, Typography } from "@mui/material";
import { Upload } from "lucide-react";

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
    <Box
      sx={{
        border: "2px dashed #4d3c63",
        borderRadius: "0.5rem",
        p: 12,
        textAlign: "center",
        transition: "border-color 0.3s",
        minHeight: "400px",
        display: "flex",
        flexDirection: "column",
        "&:hover": {
          borderColor: "var(--primary-color)",
        },
      }}
    >
      {selectedFile && previewUrl ? (
        <Box
          sx={{
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            justifyContent: "center",
            flex: 1,
            width: "100%",
          }}
        >
          <img
            src={previewUrl}
            alt="Preview"
            className={`max-w-full object-contain rounded-lg cursor-pointer transition-all duration-300 ${
              isZoomed ? "max-h-screen" : "max-h-96"
            }`}
            onClick={() => setIsZoomed(!isZoomed)}
          />
          <Typography
            variant="body1"
            sx={{
              mt: 4,
              fontSize: "1.125rem",
              fontWeight: 600,
              color: "white",
              textAlign: "center",
            }}
          >
            {selectedFile.name}
          </Typography>
        </Box>
      ) : (
        <>
          <Box
            sx={{
              display: "flex",
              justifyContent: "center",
              mb: 2,
            }}
          >
            <Upload
              size={64}
              color="#6b7280"
            />
          </Box>
          <Typography
            variant="body1"
            sx={{
              fontSize: "1.125rem",
              fontWeight: 600,
              color: "white",
              mb: 2,
            }}
          >
            Drag & drop a file or click to upload
          </Typography>
          <Typography
            variant="body2"
            sx={{
              color: "#9ca3af",
              mb: 2,
            }}
          >
            PNG, JPG, or GIF up to 10MB
          </Typography>
        </>
      )}
      <Button
        onClick={handleButtonClick}
        disabled={isProcessing}
        sx={{
          mt: 2,
          alignSelf: "center",
          width: "auto",
          maxWidth: "200px",
          height: "2rem",
          px: 3,
          backgroundColor: "var(--primary-color)",
          color: "#111714",
          fontSize: "0.8rem",
          fontWeight: 600,
          borderRadius: "0.375rem",
          "&:hover": {
            backgroundColor: "var(--primary-color)",
            opacity: 0.9,
          },
          transition: "all 0.2s",
        }}
      >
        Browse Files
      </Button>
      <input
        ref={fileInputRef}
        type="file"
        accept="image/*"
        onChange={handleFileInputChange}
        style={{ display: "none" }}
        disabled={isProcessing}
      />
    </Box>
  );
};

export default FileUpload;
