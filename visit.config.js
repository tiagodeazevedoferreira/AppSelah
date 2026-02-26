import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { VitePWA } from 'vite-plugin-pwa' // opcional, se quiser PWA

export default defineConfig({
  plugins: [
    react(),
    // VitePWA({ registerType: 'autoUpdate' }) // descomente se quiser PWA
  ],
  base: '/AppSelah/', // nome do repositório + barra (obrigatório para GitHub Pages)
  root: '.', // já é padrão
  build: {
    outDir: 'dist',
  },
})