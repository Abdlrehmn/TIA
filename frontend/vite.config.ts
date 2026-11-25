import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import { defineConfig } from "vite";

// The dev port must stay fixed: tauri.conf.json points devUrl at it.
export default defineConfig({
  plugins: [react(), tailwindcss()],
  clearScreen: false,
  server: {
    host: "127.0.0.1",
    origin: "http://localhost:1420",
    port: 1420,
    strictPort: true,
  },
});
