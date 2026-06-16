import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react' // or your framework plugin

export default defineConfig({
  plugins: [react()],
  server: {
    allowedHosts: [
      'plunging-marital-unsafe.ngrok-free.dev'
    ]
  }
})
