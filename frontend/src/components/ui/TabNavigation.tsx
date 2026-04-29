import React from 'react';
import { Box } from '@mui/material';
import type { SxProps, Theme } from '@mui/material';
import CustomButton from './CustomButton';

interface Tab {
  id: string;
  label: string;
}

interface TabNavigationProps {
  tabs: Tab[];
  activeTab: string;
  onTabChange: (tabId: string) => void;
  containerSx?: SxProps<Theme>;
  tabsSx?: SxProps<Theme>;
  buttonSx?: SxProps<Theme>;
  activeButtonSx?: SxProps<Theme>;
}

const TabNavigation: React.FC<TabNavigationProps> = ({
  tabs,
  activeTab,
  onTabChange,
  containerSx,
  tabsSx,
  buttonSx,
  activeButtonSx,
}) => {
  return (
    <Box
      sx={{
        borderBottom: '1px solid',
        borderColor: 'divider',
        px: 1,
        ...(containerSx || {}),
      }}
    >
      <Box
        sx={{
          display: 'flex',
          mb: '-1px',
          gap: 4,
          ...(tabsSx || {}),
        }}
      >
        {tabs.map((tab) => (
          <CustomButton
            key={tab.id}
            variant="tab"
            active={activeTab === tab.id}
            onClick={() => onTabChange(tab.id)}
            sx={
              [
                ...(buttonSx ? [buttonSx] : []),
                ...(activeTab === tab.id && activeButtonSx ? [activeButtonSx] : []),
              ] as SxProps<Theme>
            }
          >
            {tab.label}
          </CustomButton>
        ))}
      </Box>
    </Box>
  );
};

export default TabNavigation;
