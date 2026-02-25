import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App.jsx'          // ← relativo à raiz
import './App.css'                   // ← relativo à raiz

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
)