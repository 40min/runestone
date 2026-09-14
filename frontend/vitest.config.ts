import { fileURLToPath, URL } from "node:url";
import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  // vite-plugin-pwa's virtual registration module only exists when the plugin
  // runs (production builds); alias it to the no-op stub for tests.
  resolve: {
    alias: [
      {
        find: "virtual:pwa-register/react",
        replacement: fileURLToPath(
          new URL("./src/test/pwa-register-stub.ts", import.meta.url),
        ),
      },
    ],
  },
  test: {
    globals: true,
    environment: "jsdom",
    setupFiles: ["./src/test/setup.ts"],
    pool: "threads",
    poolOptions: {
      threads: {
        minThreads: 2,
        maxThreads: 6, // Increased from 2 for better parallelization
        useAtomics: true,
        isolate: true, // Keep isolation for test reliability
      },
    },
    maxConcurrency: 10, // Increased from 5
    isolate: true,
    testTimeout: 10000,
    hookTimeout: 10000,
    exclude: ["node_modules/**", "dist/**", "build/**"],
    // Performance optimizations
    cache: false, // Disable cache to avoid issues
    // Ensure proper cleanup
    teardownTimeout: 5000,
  },
});
