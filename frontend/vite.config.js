import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 5173,
    proxy: {
      // Swap mock → real: uncomment when FastAPI is running on :8000
      // '/api': 'http://localhost:8000',
    },
  },
})
