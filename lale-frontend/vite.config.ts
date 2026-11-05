import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import path from 'path'

// export default defineConfig({
//   plugins: [
//     react(),
//     tailwindcss(),
//   ],
// })

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      'pdfjs-dist': path.resolve(__dirname, 'node_modules/pdfjs-dist/legacy/build/pdf.mjs'),
    },
  },
})