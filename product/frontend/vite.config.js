import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  // Polling: file-change events are unreliable inside OneDrive folders on Windows.
  server: { port: 5173, host: true, watch: { usePolling: true, interval: 300 } },
});
