import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  
  server: {
    port: 5173,
    strictPort: false,
    // For local development, proxy API calls to backend
    proxy: {
      '/api': {
        target: process.env.VITE_API_URL || 'http://localhost:8000',
        changeOrigin: true,
      },
      '/health': {
        target: process.env.VITE_API_URL || 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
  
  build: {
    outDir: 'dist',
    sourcemap: false, // Set to true for debugging, false for production
    minify: 'terser',
    chunkSizeWarningLimit: 1000,
    rollupOptions: {
      output: {
        manualChunks: {
          'react-vendor': ['react', 'react-dom', 'react-router-dom'],
          'ui-vendor': ['recharts', 'framer-motion', 'lucide-react'],
          'query': ['@tanstack/react-query'],
        },
      },
    },
  },
  
  // Expose environment variables to the frontend
  define: {
    __APP_VERSION__: JSON.stringify(process.env.npm_package_version),
  },
})

