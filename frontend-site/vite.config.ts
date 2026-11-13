import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [react()],
  server: {
    host: "127.0.0.1",
    // Polling also works in containers and restricted local development environments.
    watch: { useFsEvents: false, usePolling: true },
  },
  preview: { host: "127.0.0.1" },
});
