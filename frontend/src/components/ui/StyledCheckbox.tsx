import React from 'react';
import { Checkbox, FormControlLabel } from '@mui/material';
import type { SxProps, Theme } from '@mui/material';

interface StyledCheckboxProps {
  checked: boolean;
  onChange: (checked: boolean) => void;
  label?: string;
  indeterminate?: boolean;
  sx?: SxProps<Theme>;
  id?: string;
}

const StyledCheckbox: React.FC<StyledCheckboxProps> = ({
  checked,
  onChange,
  label,
  indeterminate = false,
  sx = {},
  id,
}) => {
  const checkbox = (
    <Checkbox
      id={id}
      checked={checked}
      indeterminate={indeterminate}
      onChange={(e) => onChange(e.target.checked)}
      sx={{
        color: '#9ca3af',
        '&.Mui-checked': {
          color: 'var(--primary-color)',
        },
        '&.MuiCheckbox-indeterminate': {
          color: 'var(--primary-color)',
        },
        ...sx,
      }}
    />
  );

  if (label) {
    return (
      <FormControlLabel
        control={checkbox}
        label={label}
        sx={{
          color: 'white',
          '& .MuiFormControlLabel-label': {
            color: 'white',
          },
        }}
      />
    );
  }

  return checkbox;
};

export default StyledCheckbox;
