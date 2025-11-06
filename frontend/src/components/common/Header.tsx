import React from 'react';
import { Link, useLocation } from 'react-router-dom';

const Header: React.FC = () => {
  const location = useLocation();

  const navItems = [
    { path: '/', label: 'Dashboard' },
    { path: '/trading', label: 'Trading' }
  ];

  return (
    <header className="bg-secondary border-b border-accent px-6 py-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center space-x-2">
          <h1 className="text-xl font-bold text-white">Turbo Sniper</h1>
          <span className="text-success text-sm">Pro</span>
        </div>
        
        <nav className="flex items-center space-x-6">
          {navItems.map((item) => (
            <Link
              key={item.path}
              to={item.path}
              className={`
                px-3 py-2 rounded-lg font-medium transition-colors
                ${location.pathname === item.path 
                  ? 'bg-primary text-white' :'text-light hover:text-white hover:bg-accent'
                }
              `}
            >
              {item.label}
            </Link>
          ))}
        </nav>

        <div className="flex items-center space-x-4">
          <div className="text-right">
            <div className="text-sm text-muted">Balance</div>
            <div className="text-success font-semibold">$12,345.67</div>
          </div>
          <div className="w-8 h-8 bg-primary rounded-full flex items-center justify-center">
            <span className="text-white text-sm font-semibold">TS</span>
          </div>
        </div>
      </div>
    </header>
  );
};

export default Header;