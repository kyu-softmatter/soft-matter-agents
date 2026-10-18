import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

// The FastAPI server (T-009) serves web/dist in production. During `npm run dev`
// the Vite dev server forwards API and WebSocket calls to it. 8765 is the launcher's port
// (tools/launcher/Launcher.cs).
const SERVER = process.env.DINO_AF_SERVER ?? "http://127.0.0.1:8765";

// The shared PC is often loaded (many sessions, review runs). With vitest's default
// worker count (one per core, 24 here) App-level tests hit timeouts; two threads pass.
// DINO_AF_TEST_WORKERS overrides the cap, e.g. on a quiet machine.
const TEST_WORKERS = Number(process.env.DINO_AF_TEST_WORKERS) || 2;

export default defineConfig({
  plugins: [react()],
  build: {
    // the 3D trajectory viewer (T-022) is a lazy chunk with three.js, about 563 kB
    chunkSizeWarningLimit: 700,
  },
  server: {
    // The proxy passes the browser's Origin (http://localhost:5173) on; the server only
    // accepts it when started with `--dev-origin http://localhost:5173` (T-009c). The port
    // is pinned so that origin stays true; the Origin header is never rewritten here,
    // which would bypass the server's origin check.
    host: "localhost",
    port: 5173,
    strictPort: true,
    proxy: {
      "/api": SERVER,
      "/ws": { target: SERVER, ws: true },
    },
  },
  test: {
    environment: "jsdom",
    setupFiles: ["./src/test/setup.ts"],
    // Fork workers time out starting on the loaded shared PC; a few threads are enough.
    pool: "threads",
    maxWorkers: TEST_WORKERS,
    // App-level tests (login gate, lazy screen, client, fake socket) do several awaited
    // steps; under load 5 s is not enough. A passing test still ends as soon as it is done.
    testTimeout: 15_000,
    hookTimeout: 15_000,
  },
});
