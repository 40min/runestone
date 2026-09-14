import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.tsx'
import PwaUpdatePrompt from './components/PwaUpdatePrompt.tsx'
import { AuthProvider } from './context/AuthContext.tsx'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <AuthProvider>
      <App />
      <PwaUpdatePrompt />
    </AuthProvider>
  </StrictMode>,
)
