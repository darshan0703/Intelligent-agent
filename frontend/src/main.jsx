import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.jsx'
import { KioskProvider } from './context/KioskContext'
import { CartProvider } from "./context/CartContext";

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <KioskProvider>
      <CartProvider>
        <App />
      </CartProvider>
    </KioskProvider>
  </StrictMode>,
)