import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App.tsx';
import './styles/index.css';

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