import React, { useState } from 'react';
import { Box, Modal } from '@mui/material';
import { X } from 'lucide-react';

interface UploadedImage {
  id: string;
  url: string;
}

interface ImageSidebarProps {
  images: UploadedImage[];
}

export const ImageSidebar: React.FC<ImageSidebarProps> = ({ images }) => {
  const [selectedImage, setSelectedImage] = useState<string | null>(null);

  const handleThumbnailClick = (url: string) => {
    setSelectedImage(url);
  };

  const handleCloseModal = () => {
    setSelectedImage(null);
  };

  if (images.length === 0) {
    return null;
  }

  return (
    <>
      <Box
        sx={{
          // Keep thumbnails very small so they don't steal horizontal space on mobile.
          width: { xs: '32px', sm: '40px', md: '48px' },
          display: 'flex',
          flexDirection: 'column',
          gap: 0.75,
          ml: { xs: 1, md: 2 },
          overflowY: 'auto',
          flexShrink: 0,
        }}
      >
        {images.map((image) => (
          <Box
            key={image.id}
            onClick={() => handleThumbnailClick(image.url)}
            sx={{
              width: '100%',
              aspectRatio: '1',
              borderRadius: '4px',
              overflow: 'hidden',
              cursor: 'pointer',
              border: '1px solid #4d3c63',
              transition: 'border-color 0.2s',
              '&:hover': {
                borderColor: 'var(--primary-color)',
              },
            }}
          >
            <img
              src={image.url}
              alt="Uploaded"
              style={{
                width: '100%',
                height: '100%',
                objectFit: 'cover',
              }}
            />
          </Box>
        ))}
      </Box>

      {/* Full-size image modal */}
      <Modal
        open={selectedImage !== null}
        onClose={handleCloseModal}
        sx={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
        }}
      >
        <Box
          sx={{
            position: 'relative',
            maxWidth: '90vw',
            maxHeight: '90vh',
            outline: 'none',
          }}
        >
          <Box
            onClick={handleCloseModal}
            sx={{
              position: 'absolute',
              top: 10,
              right: 10,
              cursor: 'pointer',
              backgroundColor: 'rgba(0, 0, 0, 0.5)',
              borderRadius: '50%',
              padding: '8px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              zIndex: 1,
            }}
          >
            <X size={24} color="white" />
          </Box>
          {selectedImage && (
            <img
              src={selectedImage}
              alt="Full size"
              style={{
                maxWidth: '100%',
                maxHeight: '90vh',
                objectFit: 'contain',
                borderRadius: '8px',
              }}
            />
          )}
        </Box>
      </Modal>
    </>
  );
};
