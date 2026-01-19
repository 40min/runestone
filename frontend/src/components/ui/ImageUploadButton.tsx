import React, { useRef } from 'react';
import { Plus } from 'lucide-react';
import CustomButton from './CustomButton';

interface ImageUploadButtonProps {
  onFileSelect: (file: File) => void;
  disabled?: boolean;
}

const ImageUploadButton: React.FC<ImageUploadButtonProps> = ({ onFileSelect, disabled = false }) => {
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file && file.type.startsWith('image/')) {
      onFileSelect(file);
    } else if (file) {
      alert('Please select an image file');
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
        sx={{
          minWidth: { xs: '48px', md: '56px' },
          height: { xs: '48px', md: '56px' },
          borderRadius: '12px',
        }}
      >
        <Plus size={20} />
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
