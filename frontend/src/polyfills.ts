// src/polyfills.ts
import { Buffer } from 'buffer';

// Polyfill Buffer globally
if (typeof window !== 'undefined') {
  window.Buffer = Buffer;
  window.global = window;
  window.process = window.process || { env: {} };
  
  // Ensure globalThis has Buffer
  (globalThis as any).Buffer = Buffer;
}

