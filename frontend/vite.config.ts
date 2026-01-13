import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import tagger from "@dhiwise/component-tagger";
import { NodeGlobalsPolyfillPlugin } from '@esbuild-plugins/node-globals-polyfill';
import { nodePolyfills } from 'vite-plugin-node-polyfills';
import nodeResolve from '@rollup/plugin-node-resolve'; 
import path from 'path'; 

export default defineConfig({
  build: {
    outDir: "build",
    rollupOptions: {
      external: ['@solana-mobile/wallet-adapter-mobile'],
    },
  },
  plugins: [
    react(),
    tagger(),
    nodePolyfills({
      include: ['buffer', 'process'],
      globals: {
        Buffer: true,
        process: true,
      },
    }),
    nodeResolve({
      browser: true,
      preferBuiltins: false,
    }), 
  ],
  define: {
    'process.env.NODE_DEBUG': 'false',
    'process.env': {}, 
    global: 'globalThis',
  },
  resolve: {
    alias: {
      buffer: 'buffer/',
      process: 'process/browser',
      '@': path.resolve(__dirname, './src'), 
      '@components': path.resolve(__dirname, './src/components'),
      '@pages': path.resolve(__dirname, './src/pages'),
      '@assets': path.resolve(__dirname, './src/assets'),
      '@constants': path.resolve(__dirname, './src/constants'),
      '@styles': path.resolve(__dirname, './src/styles'),
    },
  },
  server: {
    port: 4028, 
    host: "0.0.0.0",
    strictPort: true,
    allowedHosts: ['.amazonaws.com', '.builtwithrocket.new']
  },
  optimizeDeps: {
    include: ['buffer', 'process'],
    esbuildOptions: {
      define: {
        global: 'globalThis'
      },
      plugins: [
        NodeGlobalsPolyfillPlugin({
          process: true,
          buffer: true,
        }),
      ]
    }
  }
});

