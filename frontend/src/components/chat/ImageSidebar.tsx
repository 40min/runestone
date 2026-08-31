import React, { useState } from 'react';
import { Box, Dialog, IconButton } from '@mui/material';
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
        {images.map((image, index) => (
          <IconButton
            key={image.id}
            aria-label={`View uploaded image ${index + 1}`}
            onClick={() => setSelectedImage(image.url)}
            sx={{
              width: '100%',
              aspectRatio: '1',
              borderRadius: '4px',
              overflow: 'hidden',
              p: 0,
              border: '1px solid rgba(99, 114, 173, 0.5)',
              transition: 'border-color 0.2s',
              '&:hover': {
                borderColor: 'var(--primary-color)',
              },
            }}
          >
            <Box
              component="img"
              src={image.url}
              alt=""
              sx={{
                width: '100%',
                height: '100%',
                objectFit: 'cover',
              }}
            />
          </IconButton>
        ))}
      </Box>

      {/* Full-size image dialog */}
      <Dialog
        open={selectedImage !== null}
        onClose={handleCloseModal}
        aria-label="Uploaded image preview"
        maxWidth="md"
        sx={{
          '& .MuiBackdrop-root': {
            bgcolor: 'rgba(2, 6, 23, 0.85)',
            backdropFilter: 'blur(12px)',
          },
        }}
        PaperProps={{
          sx: {
            bgcolor: 'transparent',
            boxShadow: 'none',
            overflow: 'hidden',
            position: 'relative',
            maxWidth: '90vw',
          },
        }}
      >
        <IconButton
          aria-label="Close image preview"
          onClick={handleCloseModal}
          sx={{
            position: 'absolute',
            top: 10,
            right: 10,
            color: 'white',
            backgroundColor: 'rgba(0, 0, 0, 0.5)',
            padding: '8px',
            zIndex: 1,
            '&:hover': {
              backgroundColor: 'rgba(0, 0, 0, 0.7)',
            },
          }}
        >
          <X size={24} />
        </IconButton>
        {selectedImage && (
          <img
            src={selectedImage}
            alt="Full size"
            style={{
              maxWidth: '90vw',
              maxHeight: '90vh',
              objectFit: 'contain',
              borderRadius: '8px',
            }}
          />
        )}
      </Dialog>
    </>
  );
};
