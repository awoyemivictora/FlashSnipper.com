// components/AutoSellProgress.tsx
import React, { useState, useEffect } from 'react';

interface AutoSellProgressProps {
  sellStrategy: any;
  currentProgress: number;
  totalTokens: number;
  soldTokens: number;
  estimatedProfit: number;
}

const AutoSellProgress: React.FC<AutoSellProgressProps> = ({
  sellStrategy,
  currentProgress,
  totalTokens,
  soldTokens,
  estimatedProfit
}) => {
  const [phases, setPhases] = useState([
    { name: 'Monitoring', status: 'active', progress: 0 },
    { name: 'Target Reached', status: 'pending', progress: 0 },
    { name: 'Partial Sell 1', status: 'pending', progress: 0 },
    { name: 'Partial Sell 2', status: 'pending', progress: 0 },
    { name: 'Complete', status: 'pending', progress: 0 }
  ]);

  useEffect(() => {
    // Update phases based on progress
    const updatedPhases = [...phases];
    if (currentProgress >= 20) updatedPhases[0].status = 'completed';
    if (currentProgress >= 40) updatedPhases[1].status = 'completed';
    if (currentProgress >= 60) updatedPhases[2].status = 'completed';
    if (currentProgress >= 80) updatedPhases[3].status = 'completed';
    if (currentProgress >= 100) updatedPhases[4].status = 'completed';
    setPhases(updatedPhases);
  }, [currentProgress]);

  return (
    <div className="bg-dark-2 rounded-xl p-6 border border-gray-800/50">
      <div className="flex items-center justify-between mb-6">
        <h3 className="text-white font-bold text-xl">Auto-Sell Progress</h3>
        <div className="px-3 py-1 bg-gradient-to-r from-emerald-500/20 to-teal-500/20 rounded-full border border-emerald-500/30">
          <span className="text-sm font-medium text-emerald-400">
            {sellStrategy.type} Strategy
          </span>
        </div>
      </div>

      {/* Progress bar */}
      <div className="mb-8">
        <div className="flex justify-between text-sm text-gray-400 mb-2">
          <span>Sell Progress</span>
          <span>{currentProgress}%</span>
        </div>
        <div className="h-2 bg-gray-800 rounded-full overflow-hidden">
          <div
            className="h-full bg-gradient-to-r from-emerald-500 via-teal-500 to-green-500 transition-all duration-500 ease-out"
            style={{ width: `${currentProgress}%` }}
          />
        </div>
      </div>

      {/* Token stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
        <div className="bg-gray-900/30 rounded-lg p-3">
          <div className="text-sm text-gray-400 mb-1">Total Tokens</div>
          <div className="text-white font-bold">
            {totalTokens.toLocaleString()}
          </div>
        </div>
        <div className="bg-gray-900/30 rounded-lg p-3">
          <div className="text-sm text-gray-400 mb-1">Sold Tokens</div>
          <div className="text-emerald-400 font-bold">
            {soldTokens.toLocaleString()}
          </div>
        </div>
        <div className="bg-gray-900/30 rounded-lg p-3">
          <div className="text-sm text-gray-400 mb-1">Remaining</div>
          <div className="text-yellow-400 font-bold">
            {(totalTokens - soldTokens).toLocaleString()}
          </div>
        </div>
        <div className="bg-gray-900/30 rounded-lg p-3">
          <div className="text-sm text-gray-400 mb-1">Estimated Profit</div>
          <div className="text-green-400 font-bold">
            {estimatedProfit.toFixed(4)} SOL
          </div>
        </div>
      </div>

      {/* Sell phases */}
      <div className="space-y-4">
        <h4 className="text-white font-bold">Sell Phases</h4>
        {phases.map((phase, index) => (
          <div key={index} className="flex items-center gap-3">
            <div className={`w-8 h-8 rounded-full flex items-center justify-center ${
              phase.status === 'completed' ? 'bg-emerald-500' :
              phase.status === 'active' ? 'bg-amber-500 animate-pulse' :
              'bg-gray-800'
            }`}>
              {phase.status === 'completed' ? (
                <svg className="w-4 h-4 text-white" fill="currentColor" viewBox="0 0 20 20">
                  <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
                </svg>
              ) : phase.status === 'active' ? (
                <div className="w-2 h-2 bg-white rounded-full" />
              ) : (
                <span className="text-xs text-gray-400">{index + 1}</span>
              )}
            </div>
            <div className="flex-1">
              <div className="text-white">{phase.name}</div>
              <div className="text-xs text-gray-400">
                {phase.status === 'completed' ? 'Completed' :
                 phase.status === 'active' ? 'In Progress' :
                 'Pending'}
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};

export default AutoSellProgress;

