// OWNER: P4
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: { port: 5173 },
  // Two pages: the dashboard and the pitch slides (served at /slides.html, offline like everything else).
  build: { rollupOptions: { input: { main: "index.html", slides: "slides.html" } } },
});
