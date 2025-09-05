import React from 'react';
import { Diamond } from 'lucide-react';

const Header: React.FC = () => {
  return (
    <header className="flex items-center justify-between whitespace-nowrap border-b border-solid border-b-[#3a2d4a] px-10 py-3">
      <div className="flex items-center gap-4 text-white">
        <Diamond className="size-6 text-[var(--primary-color)]" />
        <h1 className="text-white text-xl font-bold leading-tight tracking-[-0.015em]">Runestone</h1>
      </div>
      <div className="flex flex-1 justify-end gap-4 items-center">
      </div>
    </header>
  );
};

export default Header;