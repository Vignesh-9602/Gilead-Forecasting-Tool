import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],

  server: {
    proxy: {
      '/api': {
        target: 'http://localhost:8000',  // ← change port to match your backend
        changeOrigin: true,
        secure: false,
      }
    }
  },

  build: {
    outDir: 'build',
    esbuild: {
      loader: 'jsx',
      include: /src\/.*\.[jt]sx?$/,
      exclude: [],
    },
  },

  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: './src/__test__/setup.js',
  },
});