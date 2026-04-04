import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  base: "/admin/",
  server: {
    host: "0.0.0.0",
    port: 5174,
    allowedHosts: ["matsushi.xyz"],
    proxy: {
      "/api/": {
        target: "http://localhost:8000",
        changeOrigin: true,
      },
    },
  },
});
