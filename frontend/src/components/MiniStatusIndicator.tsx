// components/MiniStatusIndicator.tsx
import React from 'react';

interface MiniStatusIndicatorProps {
  launchId: string;
  status: string;
  transactions: number;
  volume: number;
  onOpenDashboard: () => void;
}

const MiniStatusIndicator: React.FC<MiniStatusIndicatorProps> = ({
  launchId,
  status,
  transactions,
  volume,
  onOpenDashboard
}) => {
  return (
    <div className="fixed bottom-4 right-4 z-40">
      <button
        onClick={onOpenDashboard}
        className="bg-gradient-to-br from-gray-900 to-dark-2 rounded-xl p-4 border border-gray-800/50 shadow-2xl hover:border-purple-500/50 transition-all duration-200 group"
      >
        <div className="flex items-center gap-3">
          <div className="relative">
            <div className="w-10 h-10 bg-gradient-to-br from-purple-500 to-pink-500 rounded-lg flex items-center justify-center">
              <svg className="w-5 h-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
              </svg>
            </div>
            <div className="absolute -top-1 -right-1 w-3 h-3 bg-emerald-500 rounded-full border-2 border-dark-2 animate-pulse" />
          </div>
          <div className="text-left">
            <div className="text-white font-bold text-sm">Launch Active</div>
            <div className="text-xs text-gray-400">
              {transactions} txs • {volume.toFixed(2)} SOL
            </div>
          </div>
        </div>
        
        {/* Progress indicator */}
        <div className="mt-3 h-1 bg-gray-800 rounded-full overflow-hidden">
          <div className="h-full bg-gradient-to-r from-purple-500 to-pink-500 animate-pulse" style={{ width: '60%' }} />
        </div>
        
        {/* Floating badge */}
        <div className="absolute -top-2 -right-2 px-2 py-1 bg-gradient-to-r from-emerald-500 to-teal-500 text-white text-xs font-bold rounded-full border border-emerald-400/30 shadow-lg">
          LIVE
        </div>
      </button>
    </div>
  );
};

export default MiniStatusIndicator;

