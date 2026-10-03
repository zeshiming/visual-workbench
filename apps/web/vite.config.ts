import { fileURLToPath, URL } from "node:url";

import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";
import vueDevTools from "vite-plugin-vue-devtools";
import tailwindcss from "@tailwindcss/vite";

const BACKEND_PORT = 8000;

// https://vite.dev/config/
export default defineConfig({
  plugins: [
    vue(),
    vueDevTools(),
    tailwindcss(),
  ],
  resolve: {
    conditions: ["development", "import", "module", "browser", "default"],
    alias: {
      "@": fileURLToPath(new URL("./src", import.meta.url)),
    },
  },
  server: {
    proxy: {
      "/api": { target: `http://localhost:${BACKEND_PORT}`, changeOrigin: true },
      "/health": { target: `http://localhost:${BACKEND_PORT}`, changeOrigin: true },
      "/__reload": { target: `http://localhost:${BACKEND_PORT}`, changeOrigin: true },
    },
  },
});
