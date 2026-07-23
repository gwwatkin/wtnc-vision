import { defineConfig } from 'vitest/config';
import preact from '@preact/preset-vite';

export default defineConfig({
  root: '.',
  plugins: [preact()],
  resolve: {
    // Prefer TypeScript sources over old .js files that coexist during the Wave A→C migration.
    // Vite's default order puts .js before .ts/.tsx; we invert that so extension-less imports
    // pick up the new .ts/.tsx stubs/implementations, leaving the old .js untouched (task9 deletes them).
    extensions: ['.mjs', '.mts', '.ts', '.tsx', '.js', '.jsx', '.json'],
  },
  build: {
    outDir: 'dist',
    rollupOptions: {
      input: {
        index:   'index.html',
        collect: 'collect.html',
        view:    'view.html',
      },
    },
  },
  publicDir: 'public',
  test: {
    environment: 'happy-dom',
    setupFiles: ['./vitest.setup.ts'],
    include: ['tests/**/*.test.ts'],
  },
});
