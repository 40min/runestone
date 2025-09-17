import React from 'react';
import { Box } from '@mui/material';
import CustomButton from './CustomButton';

interface Tab {
  id: string;
  label: string;
}

interface TabNavigationProps {
  tabs: Tab[];
  activeTab: string;
  onTabChange: (tabId: string) => void;
}

const TabNavigation: React.FC<TabNavigationProps> = ({
  tabs,
  activeTab,
  onTabChange,
}) => {
  return (
    <Box sx={{ borderBottom: '1px solid #4d3c63' }}>
      <Box sx={{ display: 'flex', mb: '-1px', gap: 8 }}>
        {tabs.map((tab) => (
          <CustomButton
            key={tab.id}
            variant="tab"
            active={activeTab === tab.id}
            onClick={() => onTabChange(tab.id)}
          >
            {tab.label}
          </CustomButton>
        ))}
      </Box>
    </Box>
  );
};

export default TabNavigation;