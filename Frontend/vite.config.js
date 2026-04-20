import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  build: {
    outDir: 'build',
    esbuild: {
      loader: {
        '.js': 'jsx', // Ensures JSX syntax is parsed in .js files
      },
    },
  },
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: './src/__test__/setup.js',
  },
})
