// components/PerformanceMetrics.tsx
import React from 'react';
import { LineChart, Line, BarChart, Bar, AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';

interface PerformanceMetricsProps {
  transactions: any[];
  botActivities: any[];
}

const PerformanceMetrics: React.FC<PerformanceMetricsProps> = ({ transactions, botActivities }) => {
  // Process data for charts
  const volumeData = React.useMemo(() => {
    const hourlyData: any = {};
    transactions.forEach(tx => {
      const hour = new Date(tx.timestamp).getHours();
      hourlyData[hour] = (hourlyData[hour] || 0) + (tx.amount || 0);
    });
    
    return Object.entries(hourlyData).map(([hour, volume]) => ({
      hour: `${hour}:00`,
      volume: Number(volume)
    }));
  }, [transactions]);

  const botPerformanceData = React.useMemo(() => {
    const performanceByBot: Record<string, any> = {};
    
    botActivities.forEach(bot => {
      if (!performanceByBot[bot.botId]) {
        performanceByBot[bot.botId] = {
          botId: bot.botId,
          publicKey: bot.publicKey.slice(0, 8) + '...',
          buys: 0,
          totalAmount: 0,
          profits: 0
        };
      }
      
      if (bot.action === 'buy') {
        performanceByBot[bot.botId].buys++;
        performanceByBot[bot.botId].totalAmount += bot.amount || 0;
      } else if (bot.action === 'sell' && bot.profit) {
        performanceByBot[bot.botId].profits += bot.profit;
      }
    });
    
    return Object.values(performanceByBot);
  }, [botActivities]);

  return (
    <div className="bg-dark-2 rounded-xl p-6 border border-gray-800/50">
      <h3 className="text-white font-bold text-xl mb-6">Performance Analytics</h3>
      
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Volume over time */}
        <div className="bg-gray-900/30 rounded-lg p-4">
          <h4 className="text-white font-bold mb-4">Volume Over Time</h4>
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={volumeData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
                <XAxis dataKey="hour" stroke="#9CA3AF" />
                <YAxis stroke="#9CA3AF" />
                <Tooltip
                  contentStyle={{
                    backgroundColor: '#1F2937',
                    border: '1px solid #374151',
                    borderRadius: '0.5rem'
                  }}
                />
                <Area
                  type="monotone"
                  dataKey="volume"
                  stroke="#8B5CF6"
                  fill="url(#colorVolume)"
                  strokeWidth={2}
                />
                <defs>
                  <linearGradient id="colorVolume" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#8B5CF6" stopOpacity={0.8} />
                    <stop offset="95%" stopColor="#8B5CF6" stopOpacity={0} />
                  </linearGradient>
                </defs>
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Bot performance */}
        <div className="bg-gray-900/30 rounded-lg p-4">
          <h4 className="text-white font-bold mb-4">Bot Performance</h4>
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={botPerformanceData.slice(0, 10)}>
                <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
                <XAxis dataKey="publicKey" stroke="#9CA3AF" />
                <YAxis stroke="#9CA3AF" />
                <Tooltip
                  contentStyle={{
                    backgroundColor: '#1F2937',
                    border: '1px solid #374151',
                    borderRadius: '0.5rem'
                  }}
                />
                <Bar dataKey="profits" fill="#10B981" radius={[4, 4, 0, 0]} />
                <Bar dataKey="totalAmount" fill="#8B5CF6" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      {/* Transaction success rate */}
      <div className="mt-6 bg-gray-900/30 rounded-lg p-4">
        <h4 className="text-white font-bold mb-4">Transaction Success Rate</h4>
        <div className="flex items-center justify-between">
          <div className="text-center">
            <div className="text-3xl font-bold text-emerald-400">98.5%</div>
            <div className="text-sm text-gray-400">Success Rate</div>
          </div>
          <div className="text-center">
            <div className="text-3xl font-bold text-blue-400">
              {transactions.filter(t => t.status === 'confirmed').length}
            </div>
            <div className="text-sm text-gray-400">Confirmed</div>
          </div>
          <div className="text-center">
            <div className="text-3xl font-bold text-red-400">
              {transactions.filter(t => t.status === 'failed').length}
            </div>
            <div className="text-sm text-gray-400">Failed</div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default PerformanceMetrics;

