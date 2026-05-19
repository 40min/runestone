import React, { useEffect, useRef, useState } from "react";
import {
  Box,
  FormControl,
  MenuItem,
  Select,
  type SelectChangeEvent,
  Typography,
} from "@mui/material";
import {
  CloudUpload,
  LockKeyhole,
  RefreshCw,
  Replace,
} from "lucide-react";
import { CustomButton } from "./ui";

interface FileUploadProps {
  onFileSelect: (file: File) => void;
  isProcessing: boolean;
  recognizeOnly?: boolean;
  onRecognizeOnlyChange?: (recognizeOnly: boolean) => void;
  compact?: boolean;
  selectedFileOverride?: File | null;
}

const FileUpload: React.FC<FileUploadProps> = ({
  onFileSelect,
  isProcessing,
  recognizeOnly = false,
  onRecognizeOnlyChange,
  compact = false,
  selectedFileOverride = null,
}) => {
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [isZoomed, setIsZoomed] = useState(false);
  const [isDragging, setIsDragging] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const applySelectedFile = (file: File) => {
    if (previewUrl && typeof URL !== "undefined" && URL.revokeObjectURL) {
      URL.revokeObjectURL(previewUrl);
    }

    setSelectedFile(file);
    setPreviewUrl(URL.createObjectURL(file));
  };

  const handleFileSelect = (file: File) => {
    if (!file.type.startsWith("image/")) {
      alert("Please select an image file");
      return;
    }

    applySelectedFile(file);
    onFileSelect(file);
  };

  useEffect(() => {
    return () => {
      if (previewUrl && typeof URL !== "undefined" && URL.revokeObjectURL) {
        URL.revokeObjectURL(previewUrl);
      }
    };
  }, [previewUrl]);

  useEffect(() => {
    if (!selectedFileOverride) return;
    if (selectedFileOverride === selectedFile) return;

    if (previewUrl && typeof URL !== "undefined" && URL.revokeObjectURL) {
      URL.revokeObjectURL(previewUrl);
    }
    setSelectedFile(selectedFileOverride);
    setPreviewUrl(URL.createObjectURL(selectedFileOverride));
  }, [selectedFileOverride, selectedFile, previewUrl]);

  const handleFileInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      handleFileSelect(e.target.files[0]);
    }
  };

  const handleDrop = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setIsDragging(false);
    if (isProcessing) return;
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      handleFileSelect(e.dataTransfer.files[0]);
    }
  };

  const handleModeChange = (event: SelectChangeEvent) => {
    const mode = event.target.value;
    onRecognizeOnlyChange?.(mode === "ocr");
  };

  const triggerFilePicker = () => {
    fileInputRef.current?.click();
  };

  const triggerReanalyze = () => {
    if (selectedFile && !isProcessing) {
      onFileSelect(selectedFile);
    }
  };

  const modeDescription = recognizeOnly
    ? "OCR-only extracts text and lets you analyze later."
    : "Full analysis extracts text, identifies grammar points, and builds vocabulary.";

  if (compact) {
    return (
      <Box
        sx={{
          borderRadius: "0.75rem",
          border: "1px solid rgba(99, 114, 173, 0.35)",
          background:
            "radial-gradient(circle at 8% 8%, rgba(38, 49, 113, 0.42), rgba(7, 12, 44, 0.96))",
          p: 2,
        }}
      >
        <Box sx={{ display: "flex", gap: 1.5, alignItems: "center" }}>
          <Box
            sx={{
              width: 92,
              height: 92,
              borderRadius: "0.5rem",
              border: "1px solid rgba(140, 160, 220, 0.35)",
              overflow: "hidden",
              flexShrink: 0,
              bgcolor: "rgba(18, 24, 64, 0.75)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
            }}
          >
            {previewUrl ? (
              <img
                src={previewUrl}
                alt="Preview"
                className="h-full w-full object-cover"
              />
            ) : (
              <CloudUpload size={26} color="#6d87cf" />
            )}
          </Box>
          <Box sx={{ minWidth: 0 }}>
            <Typography
              sx={{
                color: "#f0f4ff",
                fontWeight: 700,
                lineHeight: 1.3,
                wordBreak: "break-word",
              }}
            >
              {selectedFile?.name ?? "No file selected"}
            </Typography>
            <Typography sx={{ color: "#8ea0d0", mt: 0.6, fontSize: "0.9rem" }}>
              {selectedFile ? "Uploaded" : "Upload a textbook page"}
            </Typography>
          </Box>
        </Box>

        <Box sx={{ mt: 2 }}>
          <Typography sx={{ color: "#9fb0de", mb: 0.75, fontSize: "0.85rem" }}>
            Analysis mode
          </Typography>
          <FormControl fullWidth>
            <Select
              value={recognizeOnly ? "ocr" : "full"}
              onChange={handleModeChange}
              size="small"
              disabled={isProcessing}
              sx={{
                bgcolor: "rgba(9, 14, 48, 0.85)",
                color: "#eef4ff",
                borderRadius: "0.5rem",
                "& .MuiOutlinedInput-notchedOutline": {
                  borderColor: "rgba(111, 133, 192, 0.5)",
                },
                "& .MuiSvgIcon-root": {
                  color: "#9fc0ff",
                },
              }}
            >
              <MenuItem value="full">Full analysis</MenuItem>
              <MenuItem value="ocr">OCR only</MenuItem>
            </Select>
          </FormControl>
        </Box>

        <Box sx={{ mt: 2, display: "flex", gap: 1.5 }}>
          <CustomButton
            variant="secondary"
            onClick={triggerFilePicker}
            disabled={isProcessing}
            startIcon={<Replace size={16} />}
            sx={{
              flex: 1,
              color: "#d8e2ff",
              border: "1px solid rgba(127, 148, 205, 0.6)",
              borderRadius: "0.5rem",
              "&:hover": {
                backgroundColor: "rgba(65, 84, 142, 0.22)",
              },
            }}
          >
            Replace File
          </CustomButton>
          <CustomButton
            onClick={triggerReanalyze}
            disabled={isProcessing || !selectedFile}
            startIcon={<RefreshCw size={16} />}
            sx={{ flex: 1 }}
          >
            Re-analyze
          </CustomButton>
        </Box>

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
  }

  return (
    <Box
      sx={{
        borderRadius: "0.75rem",
        border: "1px solid rgba(99, 114, 173, 0.35)",
        background:
          "radial-gradient(circle at 10% 8%, rgba(35, 50, 116, 0.38), rgba(7, 11, 39, 0.96))",
        p: { xs: 2, sm: 3 },
      }}
    >
      <Box
        sx={{
          border: "1px dashed rgba(111, 133, 192, 0.48)",
          borderRadius: "0.75rem",
          px: 2.5,
          py: 4,
          textAlign: "center",
          transition: "all 0.2s ease",
          bgcolor: isDragging ? "rgba(31, 56, 122, 0.45)" : "transparent",
        }}
        onDragOver={(e) => {
          e.preventDefault();
          setIsDragging(true);
        }}
        onDragLeave={() => setIsDragging(false)}
        onDrop={handleDrop}
      >
        {previewUrl ? (
          <Box sx={{ display: "flex", flexDirection: "column", alignItems: "center" }}>
            <img
              src={previewUrl}
              alt="Preview"
              className={`max-w-full object-contain rounded-lg cursor-pointer transition-all duration-300 ${
                isZoomed ? "max-h-screen" : "max-h-72"
              }`}
              onClick={() => setIsZoomed((prev) => !prev)}
            />
            <Typography
              sx={{
                mt: 1.5,
                color: "#ecf2ff",
                fontWeight: 700,
                wordBreak: "break-word",
              }}
            >
              {selectedFile?.name}
            </Typography>
          </Box>
        ) : (
          <>
            <CloudUpload size={52} color="#31df85" />
            <Typography
              sx={{
                mt: 2,
                color: "#ecf2ff",
                fontWeight: 600,
                fontSize: "1.15rem",
              }}
            >
              Drag and drop an image here
            </Typography>
            <Typography sx={{ mt: 0.8, color: "#96a6cf" }}>or</Typography>
          </>
        )}

        <CustomButton
          onClick={triggerFilePicker}
          disabled={isProcessing}
          sx={{
            mt: 2,
            minWidth: 150,
            height: "2.8rem",
            fontSize: "1rem",
          }}
        >
          Choose File
        </CustomButton>
      </Box>

      <Box sx={{ mt: 2 }}>
        <Typography sx={{ color: "#9fb0de", mb: 0.75, fontSize: "0.85rem" }}>
          Analysis mode
        </Typography>
        <FormControl fullWidth>
          <Select
            value={recognizeOnly ? "ocr" : "full"}
            onChange={handleModeChange}
            size="small"
            disabled={isProcessing}
            sx={{
              bgcolor: "rgba(9, 14, 48, 0.85)",
              color: "#eef4ff",
              borderRadius: "0.5rem",
              "& .MuiOutlinedInput-notchedOutline": {
                borderColor: "rgba(111, 133, 192, 0.5)",
              },
              "& .MuiSvgIcon-root": {
                color: "#9fc0ff",
              },
            }}
          >
            <MenuItem value="full">Full analysis</MenuItem>
            <MenuItem value="ocr">OCR only</MenuItem>
          </Select>
        </FormControl>

        <Typography sx={{ mt: 1, color: "#95a7d5", fontSize: "0.92rem" }}>
          {modeDescription}
        </Typography>
      </Box>

      <CustomButton
        onClick={triggerReanalyze}
        disabled={isProcessing || !selectedFile}
        startIcon={<RefreshCw size={16} />}
        fullWidth
        sx={{ mt: 2, height: "2.9rem", fontSize: "1.05rem", fontWeight: 600 }}
      >
        Analyze Page
      </CustomButton>

      <Box
        sx={{
          mt: 2.5,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          gap: 0.75,
          color: "#8ea0d1",
          textAlign: "center",
          fontSize: "0.9rem",
          px: 1,
        }}
      >
        <LockKeyhole size={14} />
        <span>Your files are processed securely and never stored permanently.</span>
      </Box>

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
