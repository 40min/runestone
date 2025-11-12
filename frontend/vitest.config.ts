import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.ts'],
    pool: 'threads',
    poolOptions: {
      threads: {
        minThreads: 1,
        maxThreads: 2,
        useAtomics: true,
      },
    },
    maxConcurrency: 5,
    isolate: true,
    testTimeout: 10000,
    hookTimeout: 10000,
  },
});
