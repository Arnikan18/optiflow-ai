import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import './index.css';
import App from './App';
import { initializeTheme } from './theme';
import { initializeUiPreferences } from './preferences';

initializeTheme();
initializeUiPreferences();

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
