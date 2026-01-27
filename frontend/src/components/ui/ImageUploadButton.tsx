import React, { useRef } from 'react';
import { Paperclip } from 'lucide-react';
import CustomButton from './CustomButton';

interface ImageUploadButtonProps {
  onFileSelect: (file: File) => void;
  onError?: (message: string) => void;
  disabled?: boolean;
}

const ImageUploadButton: React.FC<ImageUploadButtonProps> = ({ onFileSelect, onError, disabled = false }) => {
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file && file.type.startsWith('image/')) {
      onFileSelect(file);
    } else if (file) {
      if (onError) {
        onError('Please select an image file');
      }
    }
    // Reset input so same file can be selected again
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  const handleClick = () => {
    fileInputRef.current?.click();
  };

  return (
    <>
      <CustomButton
        onClick={handleClick}
        disabled={disabled}
        variant="secondary"
        sx={{
          minWidth: '40px',
          height: '40px',
          width: '40px',
          borderRadius: '10px',
          backgroundColor: 'rgba(255, 255, 255, 0.05)',
          color: '#9ca3af',
          p: 0,
          '&:hover': {
            backgroundColor: 'rgba(255, 255, 255, 0.1)',
            color: 'white',
          },
        }}
        size="small"
      >
        <Paperclip size={18} />
      </CustomButton>
      <input
        ref={fileInputRef}
        type="file"
        accept="image/*"
        onChange={handleFileChange}
        style={{ display: 'none' }}
        disabled={disabled}
      />
    </>
  );
};

export default ImageUploadButton;
