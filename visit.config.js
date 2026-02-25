import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { VitePWA } from 'vite-plugin-pwa'  // se estiver usando PWA

export default defineConfig({
  plugins: [
    react(),
    // VitePWA({ ... }) se estiver usando
  ],
  // Aponta explicitamente para os arquivos na raiz
  root: '.',                // já é padrão, mas reforça
  build: {
    outDir: 'dist',
  },
})