import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App.tsx';
import './styles/index.css';
import './polyfills';

// Test if Buffer is polyfilled
if (typeof window !== 'undefined') {
  console.log('Buffer available?', typeof window.Buffer !== 'undefined');
  console.log('Buffer.from test:', typeof Buffer !== 'undefined' ? 'Yes' : 'No');
  
  // Force polyfill if not available
  if (typeof Buffer === 'undefined') {
    console.log('Buffer not found, importing polyfill...');
    import('buffer').then(({ Buffer }) => {
      window.Buffer = Buffer;
      console.log('Buffer polyfilled successfully');
    });
  }
}

// GLOBAL AUTH EXPIRED HANDLER — RUNS ONCE, FOREVER
if (typeof window !== 'undefined') {
  window.addEventListener('auth-expired', () => {
    console.warn('JWT expired — forcing re-login');
    localStorage.removeItem('authToken');
    
    // Clean UI message + full reload = user just re-signs with wallet
    alert('Session expired. Please reconnect your wallet.');
    window.location.reload();
  });
}

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);

