// vite.config.ts
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import tagger from "@dhiwise/component-tagger";

// Import Node.js polyfills for browser compatibility
import { NodeGlobalsPolyfillPlugin } from '@esbuild-plugins/node-globals-polyfill';
// CORRECTED IMPORT: Use a default import for @rollup/plugin-node-resolve
import nodeResolve from '@rollup/plugin-node-resolve'; 
import path from 'path'; // Added for improved alias resolution later

// https://vitejs.dev/config/
export default defineConfig({
  build: {
    outDir: "build",
  },
  plugins: [
    react(),
    tagger(),
    NodeGlobalsPolyfillPlugin({
      process: true,
      buffer: true,
    }),
    // CORRECTED USAGE: Call the default import
    nodeResolve({
      // You might want to configure this plugin. Common options include:
      // browser: true, // Use the "browser" field in package.json
      // preferBuiltins: false // Don't prefer Node.js built-ins over browser polyfills
    }), 
  ],
  define: {
    'global.Buffer': 'globalThis.Buffer',
    'process.env.NODE_DEBUG': 'false',
    'process.env': {}, 
    'global': 'globalThis', 
  },
  resolve: {
    alias: {
      'buffer': 'buffer/',
      // IMPROVED ALIAS RESOLUTION: Use path.resolve for absolute paths
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