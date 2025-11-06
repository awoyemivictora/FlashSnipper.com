import React from 'react';
import { Link, useLocation } from 'react-router-dom';

interface SidebarProps {
  isOpen?: boolean;
  onToggle?: () => void;
}

const Sidebar: React.FC<SidebarProps> = ({ isOpen = true, onToggle }) => {
  const location = useLocation();

  const menuItems = [
    { path: '/', label: 'Dashboard', icon: '📊' },
    { path: '/trading', label: 'Trading Interface', icon: '💹' },
  ];

  return (
    <aside className={`bg-dark-1 border-r border-accent transition-all duration-300 ${isOpen ? 'w-64' : 'w-16'}`}>
      <div className="p-4">
        <div className="flex items-center justify-between mb-8">
          {isOpen && <span className="text-white font-semibold">Menu</span>}
          <button
            onClick={onToggle}
            className="text-muted hover:text-white transition-colors"
          >
            {isOpen ? '←' : '→'}
          </button>
        </div>

        <nav className="space-y-2">
          {menuItems.map((item) => (
            <Link
              key={item.path}
              to={item.path}
              className={`
                flex items-center space-x-3 px-3 py-2 rounded-lg transition-colors
                ${location.pathname === item.path 
                  ? 'bg-primary text-white' :'text-light hover:text-white hover:bg-accent'
                }
              `}
            >
              <span className="text-lg">{item.icon}</span>
              {isOpen && <span>{item.label}</span>}
            </Link>
          ))}
        </nav>
      </div>
    </aside>
  );
};

export default Sidebar;