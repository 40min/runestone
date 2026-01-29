import React from 'react';
import { Button } from '@mui/material';
import type { SxProps, Theme } from '@mui/material';

interface CustomButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary' | 'tab' | 'save';
  size?: 'small' | 'medium' | 'large';
  children: React.ReactNode;
  onClick?: () => void;
  disabled?: boolean;
  startIcon?: React.ReactNode;
  fullWidth?: boolean;
  sx?: SxProps<Theme>;
  active?: boolean; // For tab variant
}

const CustomButton = ({
  variant = 'primary',
  size = 'medium',
  children,
  onClick,
  disabled = false,
  startIcon,
  fullWidth = false,
  sx,
  active = false,
  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  color: _, // Omit from props spread to avoid MUI conflict
  ...props
}: CustomButtonProps) => {
  const getVariantStyles = (): SxProps<Theme> => {
    const baseStyles: SxProps<Theme> = {
      fontWeight: 'medium',
      textTransform: 'none',
      borderRadius: '0.5rem',
      transition: 'all 0.2s',
    };

    switch (variant) {
      case 'primary':
        return {
          ...baseStyles,
          backgroundColor: 'var(--primary-color)',
          color: '#111714',
          px: size === 'small' ? 2 : size === 'large' ? 4 : 3,
          py: size === 'small' ? 1 : size === 'large' ? 2 : 1.5,
          fontSize: size === 'small' ? '0.75rem' : size === 'large' ? '1rem' : '0.875rem',
          '&:hover': {
            backgroundColor: 'var(--primary-color)',
            opacity: 0.9,
            transform: 'scale(1.02)',
          },
          '&:active': {
            transform: 'scale(0.98)',
          },
        };
      case 'secondary':
        return {
          ...baseStyles,
          color: '#9ca3af',
          px: size === 'small' ? 2 : size === 'large' ? 4 : 3,
          py: size === 'small' ? 1 : size === 'large' ? 2 : 1.5,
          fontSize: size === 'small' ? '0.75rem' : size === 'large' ? '1rem' : '0.875rem',
          backgroundColor: 'transparent',
          '&:hover': {
            color: 'white',
            backgroundColor: 'rgba(156, 163, 175, 0.1)',
          },
        };
      case 'tab':
        return {
          ...baseStyles,
          px: 2,
          py: 1,
          borderRadius: 0,
          borderBottom: active ? '2px solid var(--primary-color)' : '2px solid transparent',
          color: active ? 'var(--primary-color)' : '#9ca3af',
          fontSize: '0.925rem',
          fontWeight: active ? 'bold' : 'medium',
          minWidth: 'auto',
          backgroundColor: 'transparent',
          '&:hover': {
            color: 'white',
            backgroundColor: 'rgba(255, 255, 255, 0.05)',
            borderBottomColor: active ? 'var(--primary-color)' : '#4b5563',
          },
        };
      case 'save':
        return {
          ...baseStyles,
          backgroundColor: '#10b981',
          color: 'white',
          px: size === 'small' ? 2 : size === 'large' ? 4 : 4,
          py: size === 'small' ? 1 : size === 'large' ? 2 : 2,
          fontSize: size === 'small' ? '0.75rem' : size === 'large' ? '1rem' : '0.875rem',
          fontWeight: 700,
          display: 'flex',
          alignItems: 'center',
          gap: 2,
          '&:hover': {
            backgroundColor: '#059669',
            opacity: 0.9,
            transform: 'scale(1.05)',
            boxShadow: '0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -2px rgba(0, 0, 0, 0.05)',
          },
          '&:active': {
            transform: 'scale(0.95)',
          },
        };
      default:
        return baseStyles;
    }
  };

  const getMuiVariant = (): 'contained' | 'outlined' | 'text' => {
    if (variant === 'tab' || variant === 'secondary') return 'text';
    return 'contained';
  };

  return (
    <Button
      component="button"
      variant={getMuiVariant()}
      color="primary"
      onClick={onClick}
      disabled={disabled}
      startIcon={startIcon}
      fullWidth={fullWidth}
      sx={{
        ...getVariantStyles(),
        ...(sx || {}),
      } as SxProps<Theme>}
      {...props}
    >
      {children}
    </Button>
  );
};

export default CustomButton;
