export const config = {
    api: {
        baseUrl: import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000', // Fallback
        wsUrl: (import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000').replace(/^http/, 'ws'),
        timeout: 30000,
    },
    solana: {
        rpcUrl: import.meta.env.VITE_SHFYT_RPC || 'https://api.mainnet-beta.solana.com',
        commitment: 'confirmed' as const,
    },
    features: {
        premium: true,
        customRpc: true,
        advancedFilters: true,
    },
};

// Debug log
console.log('Config loaded:', {
    baseUrl: config.api.baseUrl,
    wsUrl: config.api.wsUrl,
    rpcUrl: config.solana.rpcUrl,
});

