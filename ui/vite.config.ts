import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

// The ScoutsKit server (`scoutskit serve`) listens on 127.0.0.1:8000; the UI talks to it through this proxy.
export default defineConfig({
  plugins: [react()],
  server: { port: 5173, proxy: { "/api": { target: "http://127.0.0.1:8000", ws: true } } },
  test: { environment: "node" },
});
