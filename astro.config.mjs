import { defineConfig } from 'astro/config';

const apiTarget = process.env.ZINAB_API_TARGET ?? 'http://127.0.0.1:8000';

export default defineConfig({
  vite: {
    server: {
      proxy: {
        '/api': { target: apiTarget, changeOrigin: true },
      },
    },
    preview: {
      proxy: {
        '/api': { target: apiTarget, changeOrigin: true },
      },
    },
  },
});
